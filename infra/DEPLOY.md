# Deploying Tenax to Alibaba Cloud (ECS)

Goal: a public backend running on **Alibaba Cloud**, which the hackathon requires you to
prove with a short screen recording (separate from the demo video).

## 1. Provision an ECS instance

- Region: pick one close to you (e.g. `ap-southeast-1` Singapore).
- Image: Ubuntu 22.04 LTS, instance size ≥ 2 vCPU / 4 GB.
- Security group: allow inbound **22** (SSH), **8000** (API). (Use 80/443 + a reverse
  proxy for a nicer URL if time permits.)
- Note the public IP.

## 2. Install Docker

```bash
ssh root@<ECS_PUBLIC_IP>
curl -fsSL https://get.docker.com | sh
```

## 3. Ship the code + configure

```bash
git clone <YOUR_PUBLIC_REPO_URL> tenax && cd tenax
cp .env.example .env      # set QWEN_API_KEY (leave DATABASE_URL; compose overrides host)
```

## 4. Run the stack

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

Now hit it publicly: `http://<ECS_PUBLIC_IP>:8000/health`.

## 5. Record the proof

Screen-record a terminal showing, on the ECS box:
- `docker compose ps` (containers running on Alibaba Cloud)
- `curl` of `/health` and a `/recall` returning real data
- the Alibaba Cloud ECS console tab (instance ID + region visible)

Keep the backend reachable and free to test through the judging period (until **31 July**).

## Optional upgrades (if time allows)
- Use **Alibaba Cloud RDS for PostgreSQL** (enable the `vector` extension) instead of the
  Postgres container, and point `DATABASE_URL` at it.
- Put the API behind **80/443** with Caddy/Nginx + a domain for a cleaner demo URL.
