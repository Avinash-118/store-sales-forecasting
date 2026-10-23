# Milestone 5 – Kubernetes manifests (AKS: storesales-aks, namespace storesales-m5)

Shared cluster infrastructure already installed: ingress-nginx (LoadBalancer 20.80.114.231),
cert-manager with ClusterIssuer `letsencrypt-production`.

Apply: `kubectl apply -f k8s/` (30-ingress only after the old API ingress is removed).

| File | What it is |
|---|---|
| 00-namespace | `storesales-m5` namespace |
| 01-serviceaccount | Workload identity -> `store-app-identity` (Key Vault, Blob, ACR — same identity as M4) |
| 02-configmap | Non-secret settings; secrets stay in Key Vault |
| 10/11 api | FastAPI Deployment (2+ replicas) + internal Service `api` |
| 20/21 dashboard | Streamlit Deployment (2+ replicas) + Service |
| 30-ingress | HTTPS on storesales-dadb2908.centralus.cloudapp.azure.com, Let's Encrypt cert, http->https |
| 40-hpa | Autoscalers (api 2–4, dashboard 2–3) |
| 50-pdb | PodDisruptionBudgets (minAvailable 1) |

API probes: liveness `/healthz` = process alive only (failure -> restart);
readiness `/readyz` = model files present AND Postgres `SELECT 1` (failure -> removed from Service, no restart).
