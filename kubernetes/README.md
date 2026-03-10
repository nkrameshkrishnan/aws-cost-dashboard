# AWS Cost Dashboard — Kubernetes Manifests

Kubernetes deployment for the AWS Cost Dashboard backend. The frontend is served from **GitHub Pages** — no frontend container or Service is required.

```
Frontend  →  https://nkrameshkrishnan.github.io/aws-cost-dashboard/
Backend   →  Kubernetes (this folder)
```

---

## Architecture

```
Internet
   │
   ▼
Ingress (nginx + TLS)          ← <minikube-ip>.nip.io  (local)
   │  CORS: nkrameshkrishnan.github.io                   <sslip.io-url>     (EKS)
   ▼
backend Service (ClusterIP :80)
   ▼
backend Deployment (FastAPI :8000, 2–10 replicas, HPA)
   │         │
   ▼         ▼
postgres   redis
Service    Service
   │         │
   ▼         ▼
postgres   redis
StatefulSet StatefulSet
(20 Gi PVC)  (5 Gi PVC)
```

> **AWS/EKS:** Replace the in-cluster postgres/redis with RDS + ElastiCache,
> and set `DATABASE_URL` / `REDIS_HOST` accordingly (see notes in each file).
> The `eks-deploy.sh` script handles this automatically when you provide
> RDS/Redis endpoints via environment variables.

---

## Folder layout

```
kubernetes/
├── base/
│   ├── namespace.yaml          Namespace + Pod Security Standards
│   ├── rbac.yaml               ServiceAccounts, Role, RoleBinding
│   ├── configmap.yaml          Non-sensitive application config
│   ├── secret.yaml             Sensitive credentials (template — fill before applying)
│   └── network-policies.yaml   Default-deny + explicit allow rules
├── backend/
│   ├── deployment.yaml         FastAPI Deployment (init-container runs migrations)
│   ├── service.yaml            ClusterIP Service → port 80 → pod 8000
│   └── hpa.yaml                HPA: 2–10 replicas, CPU 70% / Memory 80%
├── postgres/
│   ├── statefulset.yaml        PostgreSQL 15 StatefulSet (20 Gi PVC)
│   └── service.yaml            Headless + ClusterIP Services
├── redis/
│   ├── statefulset.yaml        Redis 7 StatefulSet with AOF persistence (5 Gi PVC)
│   └── service.yaml            Headless + ClusterIP Services
├── ingress/
│   ├── ingress.yaml            nginx Ingress with TLS + CORS for GitHub Pages (EKS)
│   └── cert-issuer.yaml        cert-manager Let's Encrypt ClusterIssuers
└── overlays/
    └── local/                  Kustomize overlay for minikube + Docker Hub testing
        ├── kustomization.yaml
        ├── backend-patch.yaml  1 replica, lower resources, no topology spread
        ├── configmap-patch.yaml DEBUG=true, localhost CORS, ENABLE_DOCS=true
        └── ingress-local.yaml  HTTP-only ingress for minikube
```

---

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| `kubectl` | Apply manifests | kubernetes.io/docs/tasks/tools |
| `helm` | Install ingress-nginx / cert-manager | helm.sh |
| ingress-nginx | Ingress controller | see below |
| cert-manager | Automatic TLS certificates | see below |
| metrics-server | Required by HPA | see below |

```bash
# ingress-nginx
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml

# cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl wait --namespace cert-manager --for=condition=ready pod --all --timeout=120s

# metrics-server (for HPA)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

---

## First-time deploy

### Recommended: use the deploy scripts

**Local / minikube + Docker Hub (test environment):**
```bash
export DOCKERHUB_USERNAME=your-username
export DOCKERHUB_TOKEN=your-token
export AWS_ACCESS_KEY_ID=AKIA...     # optional — for Cost Explorer features
export AWS_SECRET_ACCESS_KEY=...
./scripts/minikube-deploy.sh
```

**Production: EKS + ECR:**
```bash
export DOCKERHUB_USERNAME=...        # not needed — uses ECR
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export ECR_REPOSITORY=123456789012.dkr.ecr.us-east-1.amazonaws.com/aws-cost-dashboard-backend
./scripts/eks-deploy.sh
```

Both scripts handle secrets generation, image build/push, namespace creation,
manifest templating, and rollout waiting automatically.

### Manual apply (advanced)

If you need to apply manually, the order matters:

```bash
# 1. Namespace + RBAC first
kubectl apply -f kubernetes/base/namespace.yaml
kubectl apply -f kubernetes/base/rbac.yaml

# 2. Generate and apply secrets (the deploy scripts do this automatically)
kubectl create secret generic backend-secret --namespace=aws-cost-dashboard \
  --from-literal=SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")" \
  --from-literal=JWT_SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")" \
  --from-literal=ENCRYPTION_KEY="$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")" \
  --from-literal=DATABASE_URL="postgresql://postgres:PGPASS@postgres:5432/aws_cost_dashboard" \
  --from-literal=POSTGRES_PASSWORD="PGPASS" \
  --from-literal=REDIS_PASSWORD="" \
  --from-literal=AWS_ACCESS_KEY_ID="" \
  --from-literal=AWS_SECRET_ACCESS_KEY="" \
  --from-literal=TEAMS_WEBHOOK_URL="" \
  --from-literal=EXPORT_S3_BUCKET=""

kubectl create secret generic postgres-secret --namespace=aws-cost-dashboard \
  --from-literal=POSTGRES_PASSWORD="PGPASS"

# 3. ConfigMap + network policies
kubectl apply -f kubernetes/base/configmap.yaml
kubectl apply -f kubernetes/base/network-policies.yaml

# 4. Storage
kubectl apply -f kubernetes/postgres/
kubectl apply -f kubernetes/redis/
kubectl rollout status statefulset/postgres -n aws-cost-dashboard

# 5. Backend + ingress
kubectl apply -f kubernetes/backend/
kubectl apply -f kubernetes/ingress/cert-issuer.yaml
kubectl apply -f kubernetes/ingress/ingress.yaml
```

---

## Verification

```bash
# Watch everything come up
kubectl get all -n aws-cost-dashboard -w

# Check backend rollout
kubectl rollout status deployment/backend -n aws-cost-dashboard

# Tail backend logs
kubectl logs -n aws-cost-dashboard -l app.kubernetes.io/component=backend -f

# Check TLS certificate was issued
kubectl describe certificate backend-tls -n aws-cost-dashboard

# Test the health endpoint (replace with your sslip.io URL from eks-deploy.sh output)
curl https://<nlb-ip>.sslip.io/health
```

---

## Deploying a new backend version

**Recommended: push to `main` and let GitHub Actions handle it.**
The `.github/workflows/deploy-backend.yml` workflow builds the image, pushes it to ECR,
patches the deployment tag, and runs `kubectl rollout status` automatically.

**Manual rollout (if you need to deploy without CI):**
```bash
# 1. Build and push via the production script
./scripts/build-prod.sh --push      # pushes to ECR (reads ECR_REPOSITORY from env)

# 2. Update the image tag in backend/deployment.yaml
#    Both the initContainer (migrate) and the main container must use the same tag.
#    The eks-deploy.sh script does this automatically via sed.

# 3. Apply and wait
kubectl apply -f kubernetes/backend/deployment.yaml
kubectl rollout status deployment/backend -n aws-cost-dashboard

# Emergency rollback
kubectl rollout undo deployment/backend -n aws-cost-dashboard
```

---

## Using AWS RDS + ElastiCache instead of in-cluster databases

Delete `kubernetes/postgres/` and `kubernetes/redis/` and update config:

**`base/configmap.yaml`**
```yaml
REDIS_HOST: "your-cluster.abc123.0001.use1.cache.amazonaws.com"
```

**`base/secret.yaml`**
```yaml
DATABASE_URL: <base64 of "postgresql://user:pass@your-rds-endpoint:5432/aws_cost_dashboard">
REDIS_PASSWORD: <base64 of your ElastiCache auth token, or "" if disabled>
```

Then also delete the `allow-backend-to-postgres` and `allow-backend-to-redis` NetworkPolicies and
replace them with policies that allow egress to the RDS/ElastiCache CIDR or security groups.

---

## Using IRSA on EKS (recommended over static AWS credentials)

IRSA is configured automatically by `scripts/eks-deploy.sh` when you provide
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. The EKS cluster itself is created with
OIDC enabled via `scripts/eks-cluster.yaml`.

To set it up manually:

1. Create an IAM role with the Cost Explorer + EC2 + RDS permissions from `iam-policy.json`.
2. Annotate the `backend-sa` ServiceAccount in `base/rbac.yaml`:
   ```yaml
   annotations:
     eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/awscost-backend-role
   ```
3. Remove `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from `base/secret.yaml`
   (leave the keys present but set them to empty strings, or omit them entirely).
4. Ensure `automountServiceAccountToken: true` is set on `backend-sa` (IRSA requires it —
   it is already set in `base/rbac.yaml`).

---

## Common troubleshooting

| Symptom | Check |
|---------|-------|
| Pods stuck in `Pending` | `kubectl describe pod <name> -n aws-cost-dashboard` — likely PVC or resource issue |
| `ImagePullBackOff` | Image tag wrong; on EKS verify IRSA/ECR permissions; on minikube re-run `--load` or check Docker Hub tag |
| `CrashLoopBackOff` | `kubectl logs <pod> -n aws-cost-dashboard --previous` — check SECRET_KEY length ≥ 32 chars |
| 502 from Ingress | Backend readiness probe failing — check DB connectivity |
| CORS errors | Verify `cors-allow-origin` in ingress.yaml matches GitHub Pages URL exactly |
| HPA not scaling | Confirm metrics-server is running: `kubectl top pods -n aws-cost-dashboard` |
| TLS cert not issued | `kubectl describe certificaterequest -n aws-cost-dashboard` — check DNS + firewall |
