# AWS + Canvas Runbook

## Goal

Use AI assistance to launch AWS infrastructure (Learner Lab, EC2) and get Canvas LMS running in a verifiable way.

## AI Prompts Used (Summary)

### 1. Environment Assessment
```
"Check if AWS CLI is configured. List available EC2 instances.
Show the Learner Lab status and any running resources."
```
Used Claude Code to run `aws ec2 describe-instances` and verify Learner Lab credentials.

### 2. EC2 Instance Setup
```
"Launch or verify an EC2 instance suitable for Canvas LMS development.
Requirements: Ubuntu 22.04+, t3.medium or larger, ports 80/443/3000 open,
SSH key pair configured. Follow Canvas upstream docs for system requirements."
```
Claude Code handled security group configuration, key pair verification, and instance launch.

### 3. Canvas LMS Clone + Setup
```
"SSH into the EC2 instance. Clone the Canvas LMS fork. Follow the official
Canvas Quick Start guide at doc/docker_compose.md. Use Docker Compose to
bring up the development stack. Report what works and what errors occur."
```
AI navigated the Canvas upstream documentation, identified the Docker Compose path, and executed setup commands.

## Learner Lab + EC2 Checklist

- [x] AWS Academy Learner Lab activated
- [x] AWS CLI credentials configured (from Learner Lab → AWS Details → AWS CLI)
- [x] EC2 instance running (Ubuntu, SSH enabled)
- [x] Security group: inbound SSH (22), HTTP (80), HTTPS (443), Canvas dev (3000)
- [x] SSH key pair stored locally (not committed to repo)
- [x] Canvas LMS fork cloned on instance

## Canvas LMS: Doc Path Followed

1. **Starting point**: `README.md` → links to `doc/` directory
2. **Docker Compose path**: `docker-compose/README.md` — the recommended development setup
3. **Key commands**:
   ```bash
   git clone https://github.com/Dawson2025/canvas-lms.git
   cd canvas-lms
   # Follow docker-compose setup
   docker compose up -d
   ```
4. **Dependencies**: Docker Engine, Docker Compose v2, sufficient disk (~10GB for images)

## Verification Commands and Signals

### Canvas is working when:

```bash
# 1. Docker containers are running
docker compose ps
# Expected: web, postgres, redis, canvas containers UP

# 2. Canvas responds on expected port
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/login/canvas
# Expected: 200

# 3. Database is seeded
docker compose exec web rails runner "puts Course.count"
# Expected: > 0

# 4. Health check endpoint
curl http://localhost:3000/health_check
# Expected: JSON with "status": "ok"
```

### Signals of successful setup:
- `docker compose ps` shows all containers in "Up" state
- Browser navigates to `http://<EC2-public-IP>:3000` and shows Canvas login page
- No error logs in `docker compose logs web | tail -20`

## Out of Scope

- Feature implementation (next lab — Lab 3.2)
- Production deployment or SSL configuration
- Canvas plugin development
- Database migration or schema changes

## Integration with Memory Practice

The memory system described in `agents/memory-practice.md` directly supports this AWS work:
- **Tier 2 (file-based)**: This runbook IS a persistent memory artifact — future sessions read it instead of re-discovering the AWS setup process
- **Tier 3 (knowledge graph)**: The "Agent-Driven Feature Implementation" concept (UUID: `17189ad3`) connects AWS deployment to the overall Canvas project plan
- **Progressive disclosure**: Future agents load this runbook's verification section first (~50 tokens) before diving into full setup steps

## Forward Pointer

**Next lab (Lab 3.2)**: Agent-driven feature implementation. The memory practice (progressive disclosure, durable extraction files) and this AWS environment are prerequisites. The feature implementation agent (`agents/feature-implementation.md`, to be created) will use the GitHub MCP workflow from `agents/project-creation.md` to move items through the board as implementation proceeds.
