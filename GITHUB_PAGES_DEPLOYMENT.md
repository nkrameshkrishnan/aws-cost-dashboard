# GitHub Pages Deployment Guide - Branch-Based Approach

This guide explains how to deploy the frontend to GitHub Pages using the **gh-pages branch** method (without GitHub Actions).

---

## Overview

Instead of using GitHub Actions to deploy, we use the `gh-pages` npm package to:
1. Build the frontend locally
2. Push the build output to a separate `gh-pages` branch
3. Configure GitHub to serve the site from that branch

**Advantages:**
- ✅ No workflow scope required on Personal Access Token
- ✅ Simple and straightforward
- ✅ Works on GitHub Enterprise without Actions support
- ✅ Full control over deployment timing

---

## Prerequisites

1. **Node.js 18+** installed locally
2. **API Gateway URL** from Terraform deployment
3. **Repository access** with push permissions

---

## Deployment Steps

### Step 1: Get API Gateway URL

After deploying infrastructure with Terraform:

```bash
cd infrastructure/terraform
terraform output api_gateway_url
```

Copy the output (e.g., `https://abc123xyz.execute-api.us-east-1.amazonaws.com`)

---

### Step 2: Set API Gateway URL for Build

**Option A: Set Environment Variable (Recommended)**

```bash
# For Trend Micro GitHub Enterprise
export VITE_API_BASE_URL="https://abc123xyz.execute-api.us-east-1.amazonaws.com"

# For local testing
export VITE_API_BASE_URL="http://localhost:8000"
```

**Option B: Update .env.production File**

Edit `frontend/.env.production`:

```bash
# Update this line with your actual API Gateway URL
VITE_API_BASE_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com
VITE_API_VERSION=v1
```

---

### Step 3: Install Dependencies

```bash
cd frontend
npm install
```

This will install all dependencies including `gh-pages` package.

---

### Step 4: Build and Deploy

```bash
# Set API Gateway URL (if not already set)
export VITE_API_BASE_URL="https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com"

# Build and deploy in one command
npm run deploy
```

This command:
1. Runs `tsc` to compile TypeScript
2. Runs `vite build` to create production bundle
3. Pushes the `dist` folder to `gh-pages` branch

**Expected Output:**
```
> tsc && vite build
✓ built in 3.45s
> gh-pages -d dist
Published
```

---

### Step 5: Configure GitHub Pages

**For Trend Micro GitHub Enterprise:**

1. Go to repository: https://dsgithub.trendmicro.com/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard
2. Click **Settings** → **Pages** (left sidebar)
3. Under "Build and deployment":
   - **Source:** Deploy from a branch
   - **Branch:** `gh-pages`
   - **Folder:** `/ (root)`
4. Click **Save**

**Wait 1-2 minutes** for GitHub to deploy your site.

---

### Step 6: Access Your Site

**Trend Micro GitHub Enterprise Pages URL:**

The URL format depends on your GitHub Enterprise configuration. It could be one of:

- `https://pages.dsgithub.trendmicro.com/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard/`
- `https://rameshkrishnan-narashimankrishnamurthy.dsgithub.trendmicro.com/aws-cost-dashboard/`
- Custom domain configured by your organization

Check the repository Settings → Pages to see the published URL.

---

## Update CORS Configuration

Once you know your GitHub Pages URL, update the CORS configuration:

### 1. Update Terraform Variables

Edit `infrastructure/terraform/terraform.tfvars`:

```hcl
cors_allowed_origins = [
  "https://pages.dsgithub.trendmicro.com/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard",
  "http://localhost:5173",
  "http://localhost:3000",
]
```

### 2. Reapply Terraform

```bash
cd infrastructure/terraform
terraform plan
terraform apply
```

### 3. Restart ECS Tasks (to pick up new CORS settings)

```bash
# Get cluster and service names
CLUSTER_NAME=$(terraform output -raw ecs_cluster_name)
SERVICE_NAME=$(terraform output -raw backend_service_name)

# Force new deployment
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --force-new-deployment
```

---

## Updating the Deployment

Whenever you make frontend changes:

```bash
cd frontend

# Make your changes...

# Build and deploy
export VITE_API_BASE_URL="https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com"
npm run deploy
```

The `gh-pages` branch will be automatically updated, and GitHub Pages will redeploy within 1-2 minutes.

---

## Troubleshooting

### Issue: 404 Error After Deployment

**Cause:** GitHub Pages not configured or base path mismatch

**Solution:**
1. Check Settings → Pages shows the correct branch (`gh-pages`)
2. Verify `vite.config.ts` has correct base path:
   ```typescript
   base: '/aws-cost-dashboard/',
   ```
3. Ensure repository name matches the base path

---

### Issue: Blank Page / Assets Not Loading

**Cause:** Incorrect base path in Vite config

**Solution:**
1. Check browser DevTools console for 404 errors
2. Update `frontend/vite.config.ts`:
   ```typescript
   export default defineConfig({
     base: '/aws-cost-dashboard/',  // Must match repo name
     // ...
   })
   ```
3. Rebuild and redeploy:
   ```bash
   npm run deploy
   ```

---

### Issue: CORS Errors in Browser Console

**Cause:** GitHub Pages URL not in API Gateway CORS origins

**Solution:**
1. Get your actual GitHub Pages URL from Settings → Pages
2. Add it to `terraform.tfvars` CORS origins
3. Reapply Terraform and restart ECS tasks (see above)

---

### Issue: API Calls Go to Wrong URL

**Cause:** VITE_API_BASE_URL not set during build

**Solution:**
1. Set environment variable before building:
   ```bash
   export VITE_API_BASE_URL="https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com"
   npm run deploy
   ```

2. Or update `frontend/.env.production` with correct URL

---

### Issue: gh-pages Branch Not Created

**Cause:** Git authentication issue or first-time deployment

**Solution:**
1. Ensure you're authenticated:
   ```bash
   git config --global user.email "your.email@trendmicro.com"
   git config --global user.name "Your Name"
   ```

2. Check remote is correct:
   ```bash
   git remote -v
   # Should show: origin https://dsgithub.trendmicro.com/...
   ```

3. Try deploying again:
   ```bash
   npm run deploy
   ```

---

## Verification Checklist

After deployment, verify:

- [ ] `gh-pages` branch exists in repository
- [ ] GitHub Pages is enabled in Settings → Pages
- [ ] Settings → Pages shows "Your site is published at..."
- [ ] Opening the Pages URL shows your dashboard
- [ ] Browser DevTools Network tab shows API calls to API Gateway
- [ ] No CORS errors in browser console
- [ ] Dashboard loads cost data successfully

---

## Alternative: Deploy from docs/ Folder

If you prefer to keep everything in the main branch:

### 1. Update Vite Config

Edit `frontend/vite.config.ts`:

```typescript
export default defineConfig({
  plugins: [react()],
  base: '/aws-cost-dashboard/',
  build: {
    outDir: '../docs',  // Change output directory
  },
  // ...
})
```

### 2. Update package.json

```json
{
  "scripts": {
    "deploy": "npm run build"
  }
}
```

### 3. Build

```bash
export VITE_API_BASE_URL="https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com"
npm run build
```

### 4. Commit and Push

```bash
git add ../docs
git commit -m "Deploy frontend to docs folder"
git push origin main
```

### 5. Configure GitHub Pages

Settings → Pages:
- Source: Deploy from a branch
- Branch: `main`
- Folder: `/docs`

---

## Cost Comparison

| Method | GitHub Actions | Branch-based |
|--------|----------------|--------------|
| **Setup** | More complex | Simple |
| **PAT Scope** | Requires `workflow` | Only `repo` |
| **Automation** | Automatic on push | Manual deployment |
| **Build Location** | GitHub runners | Local machine |
| **Cost** | Free (2000 mins/month) | Free |
| **Enterprise Support** | May not be available | Always works |

**Recommendation for Trend Micro:** Use branch-based deployment (this guide) since it works on all GitHub Enterprise versions.

---

## Summary

**Quick Deployment:**
```bash
# 1. Set API Gateway URL
export VITE_API_BASE_URL="https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com"

# 2. Deploy
cd frontend
npm run deploy

# 3. Configure GitHub Pages (Settings → Pages)
# - Source: Deploy from a branch
# - Branch: gh-pages
# - Folder: / (root)
```

Your frontend will be available at the GitHub Pages URL shown in repository settings!
