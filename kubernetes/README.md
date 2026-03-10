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
Ingress (nginx + TLS)          ← api.your-domain.com
   │  CORS: nkrameshkrishnan.github.io
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

> **AWS clusters:** Replace the in-cluster postgres/redis with RDS + ElastiCache
> and set `DATABASE_URL` / `REDIS_HOST` accordingly (see notes in each file).

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
└── ingress/
    ├── ingress.yaml            nginx Ingress with TLS + CORS for GitHub Pages
    └── cert-issuer.yaml        cert-manager Let's Encrypt ClusterIssuers
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

### 1 — Fill in the Secret

Edit `base/secret.yaml` and replace every `REPLACE_WITH_BASE64_ENCODED_*` placeholder:

```bash
# Encode a value
echo -n "your-value" | base64

# Generate required keys
python -c "import secrets; print(secrets.token_urlsafe(48))"           # SECRET_KEY / JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY

# DATABASE_URL (in-cluster postgres)
echo -n "postgresql://postgres:YOUR_PG_PASS@postgres:5432/aws_cost_dashboard" | base64

# AWS credentials (skip if using IRSA on EKS)
echo -n "AKIAIOSFODNN7EXAMPLE" | base64
```

### 2 — Update the Ingress host

In `ingress/ingress.yaml`, replace both occurrences of `api.your-domain.com` with your actual hostname.

### 3 — Update the backend image tag

In `backend/deployment.yaml`, replace the image tag on both the `initContainer` and main `container`:
```yaml
image: rameshnkkrishnan/aws_cost_explorer_backend:latest
```
Use the same `VERSION` from `.env.production`. Build with `./scripts/build-prod.sh --push`.

### 4 — Apply everything

```bash
# Namespace and base resources first
kubectl apply -f kubernetes/base/namespace.yaml
kubectl apply -f kubernetes/base/rbac.yaml
kubectl apply -f kubernetes/base/configmap.yaml
kubectl apply -f kubernetes/base/secret.yaml          # ← fill values first!
kubectl apply -f kubernetes/base/network-policies.yaml

# Storage (postgres + redis)
kubectl apply -f kubernetes/postgres/
kubectl apply -f kubernetes/redis/

# Wait for postgres to be ready before the backend tries to migrate
kubectl rollout status statefulset/postgres -n aws-cost-dashboard

# Backend
kubectl apply -f kubernetes/backend/

# Ingress + TLS
kubectl apply -f kubernetes/ingress/cert-issuer.yaml
kubectl apply -f kubernetes/ingress/ingress.yaml
```

Or apply all at once (order is handled by K8s dependency resolution):
```bash
kubectl apply -f kubernetes/base/ -f kubernetes/postgres/ -f kubernetes/redis/ \
              -f kubernetes/backend/ -f kubernetes/ingress/
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

# Test the health endpoint
curl https://api.your-domain.com/health
```

---

## Deploying a new backend version

```bash
# 1. Build and push the image
./scripts/build-prod.sh --push

# 2. Update the image tag in both containers in backend/deployment.yaml
#    (initContainer + main container)

# 3. Roll out
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

1. Create an IAM role with the Cost Explorer + EC2 + RDS permissions from `iam-policy.json`.
2. Annotate the service account:
   ```yaml
   # base/rbac.yaml — backend-sa
   annotations:
     eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/awscost-backend-role
   ```
3. Remove `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from `base/secret.yaml`.
4. Set `automountServiceAccountToken: true` on the `backend-sa` ServiceAccount (IRSA needs it).

---

## Common troubleshooting

| Symptom | Check |
|---------|-------|
| Pods stuck in `Pending` | `kubectl describe pod <name> -n aws-cost-dashboard` — likely PVC or resource issue |
| `ImagePullBackOff` | Image tag wrong or registry credentials missing |
| `CrashLoopBackOff` | `kubectl logs <pod> -n aws-cost-dashboard --previous` — check SECRET_KEY length ≥ 32 chars |
| 502 from Ingress | Backend readiness probe failing — check DB connectivity |
| CORS errors | Verify `cors-allow-origin` in ingress.yaml matches GitHub Pages URL exactly |
| HPA not scaling | Confirm metrics-server is running: `kubectl top pods -n aws-cost-dashboard` |
| TLS cert not issued | `kubectl describe certificaterequest -n aws-cost-dashboard` — check DNS + firewall |
