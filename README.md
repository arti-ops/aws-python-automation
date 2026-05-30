# AWS Cloud Automation Dashboard

So this is a project I built to manage AWS infrastructure without having to touch the AWS console every single time. It's a web dashboard where you can launch EC2 instances, manage storage (EBS, EFS, S3), monitor performance, and handle users — all from one place.

The backend is FastAPI (Python) and the frontend is plain HTML/CSS/JS. No React, no heavy frameworks — just clean code that gets the job done.

---

## What it does

### EC2 Instances
You can launch new instances by picking an OS (Ubuntu or Amazon Linux), choosing an instance type, and either using an existing keypair/security group or letting the app create one for you. Once launched, you can start, stop, terminate, or edit them right from the dashboard.

### Storage
Three types of storage are covered:

- **EBS** — create volumes, attach/detach them to instances, resize them, and even read/write files on them directly from the UI using SSM under the hood.
- **EFS** — create an elastic file system, mount it across all your running instances at once, and read/write files to it.
- **S3** — create and delete buckets, upload files, browse what's inside, delete individual files.

### Monitoring
There's a live activity log that records every action you take (started instance X, deleted volume Y, etc.) with timestamps. There's also a performance panel where you select an instance and it pulls CPU and network metrics from CloudWatch.

### User Management
Admins can add, edit, and delete users. There's a role system (admin vs user). Password change works, and there's a forgot-password flow that generates a reset token — useful for development/testing.

---

## Tech used

- **Backend:** Python, FastAPI, Boto3
- **Frontend:** HTML, CSS, Vanilla JavaScript
- **Auth:** Session-based (Starlette SessionMiddleware)
- **AWS:** EC2, EBS, EFS, S3, CloudWatch, SSM
- **Templates:** Jinja2

---

## Project structure

| File | Description |
|---|---|
| [newmain.py](./newmain.py) | FastAPI backend — all routes & AWS logic |
| [script.js](./script.js) | Frontend JS — API calls & UI logic |
| [style.css](./style.css) | Dark theme styles |
| [style1.css](./style1.css) | Light theme (reference) |
| [index.html](./index.html) | Main dashboard |
| [login.html](./login.html) | Login page |
| [api.py](./api.py) | API helper |


## How to run it locally

**You'll need:**
- Python 3.10 or above
- An AWS account
- AWS CLI set up on your machine

**Step 1 — Clone the repo**
```bash
git clone https://github.com/arti-ops/aws-python-automation.git
cd aws-python-automation
```

**Step 2 — Install dependencies**
```bash
pip install fastapi uvicorn boto3 python-multipart jinja2 itsdangerous
```

**Step 3 — Configure your AWS credentials**
```bash
aws configure
```
It'll ask for your Access Key, Secret Key, and region. Use `us-east-1` or whatever region you're working in.

**Step 4 — Start the server**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Step 5 — Open in your browser**
```
http://localhost:8000
```

---

## Default login

| Username | Password |
|---|---|
| `admin` | `AwsDashboard@2026` |

Please change this after you first log in. Go to Profile → Change Password.

---

## API reference

### Auth
| Method | Endpoint | What it does |
|---|---|---|
| POST | `/login` | Log in |
| GET | `/logout` | Log out |
| POST | `/forgot-password` | Get a reset token |
| POST | `/reset-password` | Reset password using the token |

### EC2
| Method | Endpoint | What it does |
|---|---|---|
| GET | `/instances` | Get all instances |
| POST | `/create` | Launch a new instance |
| POST | `/start/{id}` | Start an instance |
| POST | `/stop/{id}` | Stop an instance |
| PUT | `/edit/{id}` | Edit instance name/type/volume |
| DELETE | `/delete/{id}` | Terminate an instance |
| GET | `/performance/{id}` | Get CloudWatch metrics |

### Storage
| Method | Endpoint | What it does |
|---|---|---|
| GET | `/storage/ebs` | List all EBS volumes |
| POST | `/storage/ebs/create` | Create a new volume |
| POST | `/storage/ebs/attach` | Attach volume to an instance |
| PUT | `/storage/ebs/modify/{id}` | Resize a volume |
| DELETE | `/storage/ebs/delete/{id}` | Delete a volume |
| GET | `/efs` | List EFS file systems |
| POST | `/efs/create` | Create an EFS |
| POST | `/efs/attach-all` | Mount EFS on all running instances |
| GET | `/buckets` | List S3 buckets |
| POST | `/create-bucket` | Create a new bucket |
| POST | `/upload-file` | Upload a file to a bucket |

### Users
| Method | Endpoint | What it does |
|---|---|---|
| GET | `/users` | List all users |
| POST | `/users/create` | Add a new user |
| PUT | `/users/{username}` | Edit a user |
| DELETE | `/users/{username}` | Delete a user |
| POST | `/users/change-password` | Change your password |

---

## IAM permissions your AWS user needs

```
AmazonEC2FullAccess
AmazonEFSFullAccess
AmazonS3FullAccess
CloudWatchReadOnlyAccess
AmazonSSMFullAccess
```

---

## A few things to know

**SSM is required for EBS/EFS file operations.** When you read or write files on a volume, the app sends commands to the instance using AWS Systems Manager. For this to work, the instance needs the SSM Agent running and the `AmazonSSMManagedInstanceCore` policy attached to its IAM role.

**Users are stored in memory.** There's no database connected. If you restart the server, all users except the default admin are gone. For anything beyond dev/demo use, you'd want to hook this up to a proper database.

**Reset tokens are dev-only.** The forgot-password flow returns the token directly in the API response (no email). This is fine for testing but obviously not how you'd ship it in production.

## Author

Built by 
Shrey 
Vanshit
jayendra
Arti 
Sinchana

