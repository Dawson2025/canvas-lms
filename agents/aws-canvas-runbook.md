# AWS + Canvas Runbook

## Goal

Use AI assistance to launch AWS infrastructure and get Canvas LMS development services running on EC2.

## AI Prompts Used (Summary)

### 1. Lab Launch + EC2 Discovery
Prompt: "Open AWS Academy Learner Lab, start the lab, check for existing EC2 instances"

Used Playwright CLI (headed browser with `DISPLAY=:0`) to navigate AWS Academy. Signed in, clicked Start Lab. Then ran AWS CLI in Vocareum terminal:
```
aws ec2 describe-instances --query "Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress,InstanceType]" --output table
```
**Result**: Found existing running instance `i-02fcd3ebd3aef3e2c` at `34.207.178.212` (t2.micro).

### 2. SSH Setup + Docker Install
Prompt: "SSH into EC2 and install Docker"

Used local SSH with the Learner Lab key:
```bash
ssh -i ~/.config/secrets/aws-learnerlab.pem ubuntu@34.207.178.212
sudo apt-get update -qq && sudo apt-get install -y -qq docker.io docker-compose-v2 git
```
**Result**: Docker 29.1.3 installed. Canvas LMS fork already cloned at `~/canvas-lms`.

### 3. Canvas Docker Services
Prompt: "Add swap and start Canvas Docker Compose services"

```bash
# Add swap (t2.micro only has 957MB RAM)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile

# Start essential services
cd ~/canvas-lms
sudo docker compose up -d postgres redis
```
**Result**: PostgreSQL and Redis containers running. Full web service needs more RAM/disk.

## Learner Lab + EC2 Checklist

- [x] AWS Academy Learner Lab activated (course 165647)
- [x] Lab started — green dot confirmed, $0.3 of $50 budget used
- [x] EC2 instance running: `i-02fcd3ebd3aef3e2c` (t2.micro, Ubuntu 22.04)
- [x] SSH key stored locally at `~/.config/secrets/aws-learnerlab.pem` (NOT in repo)
- [x] Docker 29.1.3 installed and working
- [x] Canvas LMS fork cloned at `~/canvas-lms`
- [x] 2GB swap added to extend usable memory
- [x] PostgreSQL container running (port 5432)
- [x] Redis container running (port 6379)

## Canvas LMS: Doc Path Followed

1. **Starting point**: Canvas LMS `docker-compose.yml` at repo root
2. **Services**: `postgres` (custom build from `docker-compose/postgres`), `redis` (alpine), `web` (Canvas Rails app), `jobs` (delayed job worker)
3. **Config reference**: `docker-compose/` directory contains override files for each service

## Verification Commands and Signals

```bash
# SSH access
ssh -i ~/.config/secrets/aws-learnerlab.pem ubuntu@34.207.178.212

# Check containers
sudo docker ps
# Result: canvas-lms-postgres-1 (Up), canvas-lms-redis-1 (Up)

# Check resources
df -h /        # 7.6G total, 7.3G used (96%)
free -m        # 957MB RAM + 2047MB swap

# Hostname
hostname       # ip-172-31-44-0
```

### Resource Limitations Discovered

| Resource | Available | Needed for Full Stack | Impact |
|----------|-----------|----------------------|--------|
| RAM | 957 MB + 2 GB swap | ~4 GB | Web service may OOM |
| Disk | 357 MB free | ~5 GB | Can't pull full web image |
| Instance type | t2.micro | t3.medium recommended | Budget constraint |

**Verifiable checkpoint reached**: Docker services (PostgreSQL + Redis) running, Canvas code cloned, SSH access confirmed. Full web service would require instance upgrade.

## Out of Scope

- Feature implementation (next lab — Lab 3.2)
- Full Canvas web server (needs larger instance)
- Production deployment or SSL configuration
- Canvas database seeding (needs web container)

## Integration with Memory Practice

The memory system from `agents/memory-practice.md` was used throughout this AWS setup:
- **Progressive disclosure**: Checked lab dashboard overview → drilled into modules → launched lab
- **Multi-method tooling**: Playwright headed browser for AWS auth → SSH from local terminal for commands (when screenshot-based terminal was unreadable)
- **Durable files**: This runbook and the SSH key location are saved as persistent knowledge (not session-ephemeral)
- **Trajectory stores**: `canvas_browser_submission_trajectory.md` informed the screenshot workflow

## Forward Pointer

**Next lab (Lab 3.2)**: Agent-driven feature implementation. Consider upgrading to t3.medium for full Canvas stack before implementing features. Memory budget: $49.70 remaining.
