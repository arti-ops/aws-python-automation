from fastapi import (FastAPI, HTTPException, Path, Query, Request, routing, UploadFile, File)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import Annotated, Literal, Optional
import boto3
import time
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
class CreateBucketRequest(BaseModel):

    bucket_name: str
s3 = boto3.client("s3")
import hashlib
import secrets

users_db = {
    "admin": {
        "username": "admin",
        "password": hashlib.sha256("AwsDashboard@2026".encode()).hexdigest(),
        "role": "admin",
        "email": "admin@example.com"
    }
}

reset_tokens = {}

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def require_login(request: Request):
    if "user" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
 
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="aws-dashboard-secret"
)
 
app.mount("/static",
    StaticFiles(directory="static"),
    name="static"
)
 
templates = Jinja2Templates(
    directory="templates"
)
 
# ==========================================================
# AWS EC2 CLIENT
# ==========================================================
 
ec2 = boto3.client("ec2", region_name="us-east-1")
 
cloudwatch = boto3.client(
    "cloudwatch",
    region_name="us-east-1"
)
 
AMI_MAP = {
    "ubuntu": "ami-091138d0f0d41ff90",
    "amazon-linux": "ami-0cca150d127c2216f"
}
 
 
# ==========================================================
# REQUEST MODEL
# ==========================================================
 
class CreateInstanceRequest(BaseModel):
 
    os_type: Annotated[Literal["ubuntu", "amazon-linux"], Field(description="Choose operating system")]
    instance_type: Annotated[Literal["t3.micro", "t2.micro", "t3.small"],Field(description="Enter EC2 instance type")]
    keypair_mode: Annotated[Literal['existing', 'create_new'], Field(..., description=""" existing = use already avaialble AWS keypair create_new = backend creates new keypair automatically """)]
    key_name: Annotated[str | None, Field(default=None, description='Required onl if using existing keypair')]
    security_group_mode: Annotated[Literal['existing', 'create_new'], Field(..., description=""" existing = use already avaialble AWS security group create_new = backend creates new security group automatically """)]
    security_group_name: Annotated[str | None, Field(default=None, description='Required only if using existing security group')]
    instance_name: Annotated[str, Field(description="Enter EC2 instance name",examples=["MyInstance"])]
    volume_size: Annotated[int, Field(description="Enter EBS volume size in GB")] = 8
 
class UpdateInstanceRequest(BaseModel):
 
    instance_type: Annotated[Optional[str], Field(default=None)]
    instance_name: Annotated[Optional[str], Field(default=None)]
    volume_size: Annotated[Optional[int], Field(default=None, gt=0)]
 
# ==========================================================
# HOME PAGE
# ==========================================================
 
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
 
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )
 
@app.get("/dashboard", response_class=HTMLResponse)
 
async def dashboard(
    request: Request
):
 
    if "user" not in request.session:
 
        return RedirectResponse(url="/")
 
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )
 
# ==========================================================
# LOGOUT
# ==========================================================
 
@app.get("/logout")
 
async def logout(request: Request):
 
    request.session.clear()
 
    return RedirectResponse(url="/")

@app.get("/me")
async def get_me(request: Request):
    if "user" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    username = request.session["user"]
    user = users_db.get(username, {})
    return {
        "username": username,
        "role": user.get("role", "user"),
        "email": user.get("email", "")
    }

# ==========================
# USER MANAGEMENT
# ==========================

class CreateUserRequest(BaseModel):
    username: str
    password: Optional[str] = None
    email: Optional[str] = ""
    role: Optional[str] = "user"

@app.get("/users")
async def list_users(request: Request):
    require_login(request)
    return {
        "users": [
            {"username": u["username"], "role": u["role"], "email": u.get("email", "")}
            for u in users_db.values()
        ]
    }

@app.post("/users/create")
async def create_user(request: Request, data: CreateUserRequest):
    require_login(request)
    if data.username in users_db:
        raise HTTPException(status_code=400, detail="Username already exists")
    if not data.password or len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    users_db[data.username] = {
        "username": data.username,
        "password": hash_password(data.password),
        "role": data.role,
        "email": data.email
    }
    return {"message": f"User '{data.username}' created successfully"}

@app.put("/users/{username}")
async def update_user(username: str, request: Request, data: CreateUserRequest):
    require_login(request)
    if username not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    if data.password:
        if len(data.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        users_db[username]["password"] = hash_password(data.password)
    users_db[username]["role"] = data.role
    users_db[username]["email"] = data.email
    return {"message": f"User '{username}' updated successfully"}

@app.delete("/users/{username}")
async def delete_user(username: str, request: Request):
    require_login(request)
    if username not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    if username == request.session["user"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    del users_db[username]
    return {"message": f"User '{username}' deleted successfully"}

@app.post("/users/change-password")
async def change_password(request: Request, data: dict):
    require_login(request)
    username = data.get("username")
    current = data.get("current_password")
    new_pw = data.get("new_password")
    user = users_db.get(username)
    if not user or user["password"] != hash_password(current):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if not new_pw or len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    users_db[username]["password"] = hash_password(new_pw)
    return {"message": "Password changed successfully"}

# ==========================
# FORGOT / RESET PASSWORD
# ==========================

@app.post("/forgot-password")
async def forgot_password(data: dict):
    username = data.get("username")
    email = data.get("email")
    user = users_db.get(username)
    if not user or user.get("email", "").lower() != email.lower():
        raise HTTPException(status_code=404, detail="No matching account found")
    token = secrets.token_urlsafe(32)
    reset_tokens[token] = username
    return {"dev_token": token}

@app.post("/reset-password")
async def reset_password(data: dict):
    token = data.get("token")
    new_pw = data.get("new_password")
    if not token or token not in reset_tokens:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if not new_pw or len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    username = reset_tokens.pop(token)
    users_db[username]["password"] = hash_password(new_pw)
    return {"message": "Password reset successfully"}
 
# ==========================================================
# LOGIN API
# ==========================================================
 
@app.post("/login")
async def login(request: Request, data: dict):
    username = data.get("username")
    password = data.get("password")
    user = users_db.get(username)
    if user and user["password"] == hash_password(password):
        request.session["user"] = username
        return {"success": True}
    raise HTTPException(status_code=401, detail="Invalid username or password")
# ==========================================================
# LIST INSTANCES
# ==========================================================
 
@app.get("/instances")
def list_instances(request: Request):
    require_login(request) 
    try:
 
        start_time = time.time()
 
        response = ec2.describe_instances()
 
        end_time = time.time()
 
       
 
        instances = []
 
        for reservation in response.get("Reservations", []):
 
            for instance in reservation.get("Instances", []):
 
                name = "N/A"
 
                if "Tags" in instance:
 
                    for tag in instance["Tags"]:
 
                        if tag["Key"] == "Name":
                            name = tag["Value"]
 
                instances.append({
                    "instance_name": name,
                    "instance_id": instance.get("InstanceId"),
                    "state": instance.get("State", {}).get("Name"),
                    "type": instance.get("InstanceType"),
                    "public_ip": instance.get("PublicIpAddress", "N/A"),
                    "private_ip": instance.get("PrivateIpAddress", "N/A")
                })
 
        return {
             "count": len(instances), "instances": instances,
             "time_taken_seconds": round(end_time - start_time,2 )
            }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# VIEW SECURITY GROUPS
# ==========================================================
 
@app.get("/security-groups")
def list_security_groups():
 
    response = ec2.describe_security_groups()
 
    groups = []
 
    for sg in response["SecurityGroups"]:
 
        groups.append({
            "group_name": sg["GroupName"],
            "group_id": sg["GroupId"]
        })
 
    return {
        "security_groups": groups
    }
 
 
# ==========================================================
# VIEW KEYPAIRS
# ==========================================================
 
@app.get("/keypairs")
def list_keypairs():
 
    response = ec2.describe_key_pairs()
 
    keypairs = []
 
    for key in response["KeyPairs"]:
 
        keypairs.append({
            "key_name": key["KeyName"]
        })
 
    return {
        "keypairs": keypairs
    }
 
 
# ==========================================================
# VIEW OS OPTIONS
# ==========================================================
 
@app.get("/os-options")
def os_options():
 
    return {
        "available_os": [
            "ubuntu",
            "amazon-linux"
        ]
    }
 
# ==========================================================
# VIEW INSTANCE TYPES
# ==========================================================
 
@app.get("/instance-types")
def instance_types():
 
    return {
        "instance_types": [
            "t2.micro",
            "t3.micro",
            "t3.small"
        ]
    }
 
# ==========================================================
# VIEW SINGLE INSTANCE
# ==========================================================
 
@app.get("/instance/{instance_name}")
def view_instance(
 
    instance_name: str = Path(
        ...,
        description="Name tag of EC2 instance",
        examples=["MyServer"]
    )
):
 
    response = ec2.describe_instances()
 
    for reservation in response.get("Reservations", []):
 
        for instance in reservation.get("Instances", []):
 
            if "Tags" in instance:
 
                for tag in instance["Tags"]:
 
                    if (
                        tag["Key"] == "Name"
                        and tag["Value"] == instance_name
                    ):
 
                        return {
                            "instance_name": instance_name,
                            "instance_id": instance.get("InstanceId"),
                            "state": instance.get("State", {}).get("Name"),
                            "type": instance.get("InstanceType"),
                            "public_ip": instance.get(
                                "PublicIpAddress",
                                "N/A"
                            )
                        }
 
    raise HTTPException(
        status_code=404,
        detail="Instance not found"
    )
 
# ==========================================================
# SORT INSTANCES
# ==========================================================
 
@app.get("/sort")
def sort_instances(
 
    sort_by: str = Query(
        ...,
        description="Sort by instance_name, state or public_ip"
    ),
 
    order: str = Query(
        "asc",
        description="Sort order asc or desc"
    )
):
 
    valid_fields = [
        "instance_name",
        "state",
        "public_ip"
    ]
 
    if sort_by not in valid_fields:
 
        raise HTTPException(
            status_code=400,
            detail=f"Invalid field. Select from {valid_fields}"
        )
 
    if order not in ["asc", "desc"]:
 
        raise HTTPException(
            status_code=400,
            detail="Invalid order. Use asc or desc"
        )
 
    response = ec2.describe_instances()
 
    instances = []
 
    for reservation in response.get("Reservations", []):
 
        for instance in reservation.get("Instances", []):
 
            name = "N/A"
 
            if "Tags" in instance:
 
                for tag in instance["Tags"]:
 
                    if tag["Key"] == "Name":
                        name = tag["Value"]
 
            instances.append({
                "instance_name": name,
                "instance_id": instance.get("InstanceId"),
                "state": instance.get("State", {}).get("Name"),
                "public_ip": instance.get(
                    "PublicIpAddress",
                    "N/A"
                )
            })
 
    reverse_order = (
        True if order == "desc" else False
    )
 
    sorted_data = sorted(
        instances,
        key=lambda x: x.get(sort_by, ""),
        reverse=reverse_order
    )
 
    return {
        "count": len(sorted_data),
        "instances": sorted_data
    }
 
# ==========================================================
# CREATE INSTANCE
# ==========================================================
 
@app.post("/create")
def create_instance(req: CreateInstanceRequest, request: Request):
    require_login(request) 
    try:
 
        start_time = time.time()
 
        # ==========================================================
        # SECURITY GROUP LOGIC
        # ==========================================================
 
        security_group_id = None
 
        if req.security_group_mode == "existing":
 
            response = ec2.describe_security_groups()
 
            for sg in response["SecurityGroups"]:
 
                if sg["GroupName"] == req.security_group_name:
 
                    security_group_id = sg["GroupId"]
                    break
 
            if not security_group_id:
 
                raise HTTPException(
                    status_code=404,
                    detail="Security group not found"
                )
 
        else:
 
            new_sg = ec2.create_security_group(
                GroupName=f"{req.instance_name}-sg",
                Description="Auto created security group"
            )
 
            security_group_id = new_sg["GroupId"]
 
            ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
              {
                 "IpProtocol": "tcp",
                 "FromPort": 22,
                 "ToPort": 22,
                 "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
              },
              {
                 "IpProtocol": "tcp",
                 "FromPort": 80,
                 "ToPort": 80,
                 "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
              }
           ]
         )
 
        # ==========================================================
        # KEYPAIR LOGIC
        # ==========================================================
 
        private_key_material = None
        key_name = None
 
        if req.keypair_mode == "existing":
 
            key_name = req.key_name
 
            if not key_name:
 
                raise HTTPException(
                    status_code=400,
                    detail="Keypair name is required"
                )
 
        else:
 
            generated_key_name = (
                f"{req.instance_name}-keypair"
            )
 
            key_response = ec2.create_key_pair(
                KeyName=generated_key_name
            )
 
            key_name = generated_key_name
 
            private_key_material = (
                key_response["KeyMaterial"]
            )
 
            pem_file_path = f"{generated_key_name}.pem"
 
            with open(pem_file_path, "w") as pem_file: pem_file.write(private_key_material)
 
            import os
            os.chmod(pem_file_path, 0o400)
 
        # ==========================================================
        # AMI LOGIC
        # ==========================================================
 
        if req.os_type not in AMI_MAP:
 
            raise HTTPException(
                status_code=400,
                detail="Invalid OS type"
            )
 
        ami_id = AMI_MAP[req.os_type]
 
        # ==========================================================
        # CREATE EC2 INSTANCE
        # ==========================================================
 
        response = ec2.run_instances(
 
            ImageId=ami_id,
 
            InstanceType=req.instance_type,
 
            KeyName=key_name,
 
            SecurityGroupIds=[security_group_id],
 
            MinCount=1,
            MaxCount=1,
 
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/xvda",
 
                    "Ebs": {
                        "VolumeSize": req.volume_size
                    }
                }
            ],
 
            TagSpecifications=[
                {
                    "ResourceType": "instance",
 
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": req.instance_name
                        }
                    ]
                }
            ]
        )
 
        instance_id = (
            response["Instances"][0]["InstanceId"]
        )
 
        end_time = time.time()
 
        return {
            "message": "Instance creation initiated",
            "instance_id": instance_id,
            "instance_name": req.instance_name,
            "security_group_id": security_group_id,
            "key_name": key_name,
            "private_key": private_key_material,
            "time_taken_seconds": round(end_time - start_time,2)
         }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# START INSTANCE
# ==========================================================
 
@app.post("/start/{instance_id}")
def start_instance(instance_id: str, request: Request):
    require_login(request) 
    try:
 
        start_time = time.time()
 
        ec2.start_instances(
            InstanceIds=[instance_id]
        )
 
        end_time = time.time()
 
        return {
            "message": "Start request sent",
            "instance_id": instance_id,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# STOP INSTANCE
# ==========================================================
 
@app.post("/stop/{instance_id}")
def stop_instance(instance_id: str, request: Request):
    require_login(request) 
    try:
 
        start_time = time.time()
 
        ec2.stop_instances(
            InstanceIds=[instance_id]
        )
 
        end_time = time.time()
 
        return {
            "message": "Stop request sent",
            "instance_id": instance_id,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
   
 
# ==========================================================
# UPDATE INSTANCE
# ==========================================================
 
@app.put("/edit/{instance_id}")
def update_instance(instance_id: str, instance_update: UpdateInstanceRequest, request: Request):
    require_login(request)
 
    try:
 
        start_time = time.time()
 
        updated_fields = []
 
        # ==========================================================
        # UPDATE INSTANCE TYPE
        # ==========================================================
 
        if instance_update.instance_type is not None:
 
            ec2.modify_instance_attribute(
                InstanceId=instance_id,
                InstanceType={
                    "Value": instance_update.instance_type
                }
            )
 
            updated_fields.append("instance_type")
 
        # ==========================================================
        # UPDATE INSTANCE NAME TAG
        # ==========================================================
 
        if instance_update.instance_name is not None:
 
            ec2.create_tags(
                Resources=[instance_id],
                Tags=[
                    {
                        "Key": "Name",
                        "Value": instance_update.instance_name
                    }
                ]
            )
 
            updated_fields.append("instance_name")
 
        # ==========================================================
        # UPDATE EBS VOLUME SIZE
        # ==========================================================
 
        if instance_update.volume_size is not None:
 
            response = ec2.describe_instances(
                InstanceIds=[instance_id]
            )
 
            volume_id = (
                response["Reservations"][0]
                ["Instances"][0]
                ["BlockDeviceMappings"][0]
                ["Ebs"]["VolumeId"]
            )
 
            ec2.modify_volume(
                VolumeId=volume_id,
                Size=instance_update.volume_size
            )
 
            updated_fields.append("volume_size")
 
        end_time = time.time()
 
        return {
            "message": "Instance updated successfully",
            "instance_id": instance_id,
            "updated_fields": updated_fields,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
   
# ==========================================================
# DELETE INSTANCE
# ==========================================================
 
@app.delete("/delete/{instance_id}")
def delete_instance(instance_id: str, request: Request):
    require_login(request) 
    try:
 
        start_time = time.time()
 
        ec2.terminate_instances(
            InstanceIds=[instance_id]
        )
 
        end_time = time.time()
 
        return {
            "message": "Instance deleted successfully",
            "instance_id": instance_id,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
   
# ==========================================================
# PERFORMANCE METRICS
# ==========================================================
 
@app.get("/performance/{instance_id}")
def get_performance(instance_id: str):
 
    try:
 
        # CPU
 
        cpu_response = cloudwatch.get_metric_statistics(
 
            Namespace="AWS/EC2",
 
            MetricName="CPUUtilization",
 
            Dimensions=[
                {
                    "Name": "InstanceId",
                    "Value": instance_id
                }
            ],
 
            StartTime=datetime.utcnow() - timedelta(minutes=30),
 
            EndTime=datetime.utcnow(),
 
            Period=300,
 
            Statistics=["Average"]
 
        )
 
        # NETWORK IN
 
        network_in_response = cloudwatch.get_metric_statistics(
 
            Namespace="AWS/EC2",
 
            MetricName="NetworkIn",
 
            Dimensions=[
                {
                    "Name": "InstanceId",
                    "Value": instance_id
                }
            ],
 
            StartTime=datetime.utcnow() - timedelta(minutes=30),
 
            EndTime=datetime.utcnow(),
 
            Period=300,
 
            Statistics=["Average"]
 
        )
 
        # NETWORK OUT
 
        network_out_response = cloudwatch.get_metric_statistics(
 
            Namespace="AWS/EC2",
 
            MetricName="NetworkOut",
 
            Dimensions=[
                {
                    "Name": "InstanceId",
                    "Value": instance_id
                }
            ],
 
            StartTime=datetime.utcnow() - timedelta(minutes=30),
 
            EndTime=datetime.utcnow(),
 
            Period=300,
 
            Statistics=["Average"]
 
        )
 
        # DEFAULT VALUES
 
        cpu = 0
        network_in = 0
        network_out = 0
 
        # CPU DATA
 
        datapoints = cpu_response.get(
            "Datapoints",
            []
        )
 
        if datapoints:
 
            latest_cpu = sorted(
            datapoints,
             key=lambda x: x["Timestamp"])[-1]
 
            cpu = round(
             latest_cpu["Average"], 2
          )
 
        # NETWORK IN DATA
 
        network_in_points = network_in_response.get(
            "Datapoints",
            []
        )
 
        if network_in_points:
 
            latest_network_in = sorted(network_in_points,
              key=lambda x: x["Timestamp"])[-1]
 
            network_in = round(
             latest_network_in["Average"] / 1024, 2
            )
 
        # NETWORK OUT DATA
 
        network_out_points = network_out_response.get(
            "Datapoints",
            []
        )
 
        if network_out_points:
 
            latest_network_out = sorted(
             network_out_points,key=lambda x: x["Timestamp"])[-1]
 
            network_out = round(
    latest_network_out["Average"] / 1024,
    2
)
 
        return {
 
            "cpu": cpu,
 
            "ram": 0,
 
            "storage": 0,
 
            "network_in": network_in,
 
            "network_out": network_out
 
        }
 
    except Exception as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
        # ==========================================================
# AWS EFS CLIENT
# ==========================================================

efs = boto3.client(
    "efs",
    region_name="us-east-1"
)

# ==========================================================
# AWS SSM CLIENT
# ==========================================================

ssm = boto3.client(
    "ssm",
    region_name="us-east-1"
)

# ==========================================================
# EFS REQUEST MODELS
# ==========================================================

class CreateEFSRequest(BaseModel):

    file_system_name: Annotated[
        str,
        Field(
            description="Enter EFS Name",
            examples=["MyEFS"]
        )
    ]

    performance_mode: Annotated[
        Literal[
            "generalPurpose",
            "maxIO"
        ],
        Field(
            default="generalPurpose"
        )
    ] = "generalPurpose"

    throughput_mode: Annotated[
        Literal[
            "bursting",
            "elastic",
            "provisioned"
        ],
        Field(
            default="bursting"
        )
    ] = "bursting"


class UpdateEFSRequest(BaseModel):

    throughput_mode: Annotated[
        Optional[
            Literal[
                "bursting",
                "elastic",
                "provisioned"
            ]
        ],
        Field(default=None)
    ]


class AttachEFSRequest(BaseModel):

    file_system_id:str


class WriteEFSRequest(BaseModel):

    file_system_id:str

    file_name:str

    content:str


# ==========================================================
# HELPER
# ==========================================================

def get_all_instances():

    response=(
        ec2.describe_instances()
    )

    instances=[]

    for reservation in (
        response["Reservations"]
    ):

        for instance in (
            reservation["Instances"]
        ):

            if (
                instance["State"]["Name"]
                =="running"
            ):

                instances.append(
                    instance[
                        "InstanceId"
                    ]
                )

    return instances


# ==========================================================
# LIST EFS
# ==========================================================

@app.get("/efs")
def list_efs(request: Request):
    require_login(request)
    try:

        start_time=time.time()

        response=efs.describe_file_systems()

        file_systems=[]

        for fs in response["FileSystems"]:

            tags=efs.describe_tags(
                FileSystemId=
                fs["FileSystemId"]
            )

            efs_name="N/A"

            for tag in tags["Tags"]:

                if tag["Key"]=="Name":

                    efs_name=tag["Value"]

            file_systems.append({

                "file_system_name":
                efs_name,

                "file_system_id":
                fs["FileSystemId"],

                "life_cycle_state":
                fs["LifeCycleState"],

                "performance_mode":
                fs["PerformanceMode"],

                "throughput_mode":
                fs["ThroughputMode"],

                "size_bytes":
                fs["SizeInBytes"]["Value"]
            })

        end_time=time.time()

        return{

            "count":
            len(file_systems),

            "efs":
            file_systems,

            "time_taken_seconds":
            round(
                end_time-start_time,
                2
            )
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# ==========================================================
# VIEW SINGLE EFS
# ==========================================================

@app.get("/efs/{file_system_name}")
def view_efs(
    file_system_name:str
):

    response=efs.describe_file_systems()

    for fs in response["FileSystems"]:

        tags=efs.describe_tags(
            FileSystemId=
            fs["FileSystemId"]
        )

        for tag in tags["Tags"]:

            if(
                tag["Key"]=="Name"
                and
                tag["Value"]==
                file_system_name
            ):

                return{

                    "file_system_name":
                    file_system_name,

                    "file_system_id":
                    fs["FileSystemId"],

                    "state":
                    fs["LifeCycleState"],

                    "performance_mode":
                    fs["PerformanceMode"],

                    "throughput_mode":
                    fs["ThroughputMode"]
                }

    raise HTTPException(
        status_code=404,
        detail="EFS not found"
    )


# ==========================================================
# CREATE EFS
# ==========================================================

@app.post("/efs/create")
def create_efs(
    req:CreateEFSRequest
):

    try:

        start_time=time.time()

        response= efs.create_file_system(

            PerformanceMode=
            req.performance_mode,

            ThroughputMode=
            req.throughput_mode,

            Tags=[
                {
                    "Key":"Name",
                    "Value":
                    req.file_system_name
                }
            ]
        )

        file_system_id=(
            response[
                "FileSystemId"
            ]
        )

        vpcs=ec2.describe_vpcs()

        default_vpc=None

        for vpc in vpcs["Vpcs"]:

            if vpc.get(
                "IsDefault"
            ):

                default_vpc=(
                    vpc["VpcId"]
                )

                break


        subnet_response=(

            ec2.describe_subnets(
                Filters=[
                    {
                        "Name":"vpc-id",
                        "Values":
                        [default_vpc]
                    }
                ]
            )
        )

        subnets=(
            subnet_response[
                "Subnets"
            ]
        )

        sg=ec2.create_security_group(

            GroupName=
            f"{req.file_system_name}-efs-sg",

            Description=
            "Auto EFS SG",

            VpcId=
            default_vpc
        )

        sg_id=sg["GroupId"]

        ec2.authorize_security_group_ingress(

            GroupId=
            sg_id,

            IpPermissions=[
                {
                    "IpProtocol":
                    "tcp",

                    "FromPort":
                    2049,

                    "ToPort":
                    2049,

                    "IpRanges":[
                        {
                            "CidrIp":
                            "0.0.0.0/0"
                        }
                    ]
                }
            ]
        )# ==================================================
         # CREATE MOUNT TARGET IN ALL SUBNETS
         # ==================================================

        subnets = subnet_response["Subnets"]

        for subnet in subnets:

          try:

                efs.create_mount_target(

                    FileSystemId=
                    file_system_id,

                    SubnetId=
                    subnet["SubnetId"],

                    SecurityGroups=
                    [sg_id]
                )

          except Exception:

                 pass


        # =====================================
        # WAIT
        # =====================================

        time.sleep(60)

        end_time=time.time()

        return{

            "message":
            "EFS created successfully",

            "file_system_name":
            req.file_system_name,

            "file_system_id":
            file_system_id,

            "security_group":
            sg_id,

            "time_taken_seconds":
            round(
                end_time-start_time,
                2
            )
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# ==========================================================
# ATTACH EFS TO ALL
# ==========================================================

@app.post("/efs/attach-all")
def attach_efs_all(
    req:AttachEFSRequest
):

    try:

        instances= get_all_instances()

        commands=[

        "sudo yum install -y amazon-efs-utils || sudo dnf install -y amazon-efs-utils",
        
        "sudo umount -lf /mnt/efs || true",
        
        "sudo mkdir -p /mnt/efs",

        f"sudo mount -t efs -o tls {req.file_system_id}:/ /mnt/efs",

        "sleep 20",

        "mount | grep nfs",

        "df -h",

        "sudo touch /mnt/efs/data.txt",

        "sudo touch /mnt/efs/notes.txt"
        ]

        response=(
            ssm.send_command(

                InstanceIds=
                instances,

                DocumentName=
                "AWS-RunShellScript",

                Parameters={
                    "commands":
                    commands
                }
            )
        )

        return{

            "message":
            "EFS attached to all instances",

            "instances":
            instances,

            "command_id":
            response[
                "Command"
            ]["CommandId"]
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# ==========================================================
# WRITE DATA
# ==========================================================

@app.post("/efs/write")
def write_efs(
    req:WriteEFSRequest
):

    try:

        instances= get_all_instances()

        command=[

        f'echo "{req.content}" | sudo tee /mnt/efs/{req.file_name}'
        ]

        response=(
            ssm.send_command(

                InstanceIds=[
                    instances[0]
                ],

                DocumentName=
                "AWS-RunShellScript",

                Parameters={
                    "commands":
                    command
                }
            )
        )

        return{

            "message":
            "Data written successfully",

            "file":
            req.file_name,

            "written_content":
            req.content,

            "command_id":
            response[
                "Command"
            ]["CommandId"]
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# ==========================================================
# DELETE EFS
# ==========================================================

@app.delete("/efs/delete/{file_system_id}")
def delete_efs(
    file_system_id:str
):

    try:

        response= efs.describe_mount_targets(
            FileSystemId=
            file_system_id
        )

        mount_targets= response[
            "MountTargets"
        ]

        for mt in mount_targets:

            efs.delete_mount_target(

                MountTargetId=
                mt[
                    "MountTargetId"
                ]
            )

        while True:

            response= efs.describe_mount_targets(
                FileSystemId=
                file_system_id
            )

            if len(
                response[
                    "MountTargets"
                ]
            )==0:

                break

            time.sleep(5)

        efs.delete_file_system(
            FileSystemId=
            file_system_id
        )

        return{

            "message":
            "EFS deleted successfully",

            "file_system_id":
            file_system_id
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )# ==========================================================
# UPDATE EFS
# ==========================================================

@app.put("/efs/edit/{file_system_id}")
def update_efs(
    file_system_id:str,
    req:UpdateEFSRequest
):

    try:

        updated=[]

        if req.throughput_mode:

            efs.update_file_system(

                FileSystemId=
                file_system_id,

                ThroughputMode=
                req.throughput_mode
            )

            updated.append(
                "throughput_mode"
            )

        return{

            "message":
            "EFS updated successfully",

            "updated_fields":
            updated,

            "file_system_id":
            file_system_id
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )# ==========================================================
# LIST ACCESS POINTS
# ==========================================================

@app.get("/access-points")
def access_points():

    try:

        response=efs.describe_access_points()

        data=[]

        for ap in response[
            "AccessPoints"
        ]:

            data.append({

                "access_point_id":
                ap[
                    "AccessPointId"
                ],

                "file_system_id":
                ap[
                    "FileSystemId"
                ],

                "life_cycle":
                ap[
                    "LifeCycleState"
                ]
            })

        return{

            "count":
            len(data),

            "access_points":
            data
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# ==========================================================
# CREATE ACCESS POINT
# ==========================================================

@app.post(
"/access-point/create/{file_system_id}"
)
def create_access_point(
    file_system_id:str
):

    try:

        start_time=time.time()

        response=efs.create_access_point(

            FileSystemId=
            file_system_id
        )

        end_time=time.time()

        return{

            "message":
            "Access Point Created",

            "access_point_id":
            response[
                "AccessPointId"
            ],

            "time_taken_seconds":
            round(
                end_time-start_time,
                2
            )
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )# ==========================================================
# DELETE ACCESS POINT
# ==========================================================

@app.delete(
"/access-point/{access_point_id}"
)
def delete_access_point(
    access_point_id:str
):

    try:

        efs.delete_access_point(
            AccessPointId=
            access_point_id
        )

        return{

            "message":
            "Access Point Deleted",

            "access_point_id":
            access_point_id
        }

    except ClientError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        # ==========================================================
# EBS STORAGE AUTOMATION
# ==========================================================
 
 
# ==========================================================
# REQUEST MODELS
# ==========================================================
 
class CreateEBSRequest(BaseModel):
 
    instance_name: str = Field(
        ...,
        description="EC2 Instance Name"
    )
 
    size: int = Field(
        ...,
        gt=0,
        description="EBS Volume Size in GB"
    )
 
    volume_type: str = Field(
        default="gp3",
        description="gp2 | gp3 | io1 | st1"
    )
 
    tag_name: Optional[str] = Field(
        default="MyEBSVolume"
    )
 
 
class AttachEBSRequest(BaseModel):
 
    instance_name: str = Field(
        ...,
        description="EC2 Instance Name"
    )
 
    volume_id: str = Field(
        ...,
        description="EBS Volume ID"
    )
 
 
class ModifyEBSRequest(BaseModel):
 
    volume_size: int = Field(
        ...,
        gt=0,
        description="New EBS Size in GB"
    )
 
 
# ==========================================================
# HELPER FUNCTION
# GET INSTANCE DETAILS USING INSTANCE NAME
# ==========================================================
 
def get_instance_by_name(instance_name):
 
    response = ec2.describe_instances(
 
        Filters=[
            {
                "Name":"tag:Name",
                "Values":[instance_name]
            }
        ]
    )
 
    reservations = response["Reservations"]
 
    if not reservations:
 
        return None
 
    instance = reservations[0]["Instances"][0]
 
    return {
 
        "instance_id":
        instance["InstanceId"],
 
        "availability_zone":
        instance["Placement"]["AvailabilityZone"]
    }
 
 
# ==========================================================
# LIST ALL EBS VOLUMES
# ==========================================================
 
@app.get("/storage/ebs")
 
def list_ebs_volumes(request: Request):
    require_login(request)
    
    try:
 
        start_time = time.time()
 
        response = ec2.describe_volumes()
 
        volumes = []
 
        for volume in response["Volumes"]:
 
            volume_name = "N/A"
 
            attached_instance_id = (
                "Not Attached"
            )
 
            attached_instance_name = (
                "Not Attached"
            )
 
            if "Tags" in volume:
 
                for tag in volume["Tags"]:
 
                    if tag["Key"]=="Name":
 
                        volume_name=(
                            tag["Value"]
                        )
 
            if volume["Attachments"]:
 
                attached_instance_id=(
                    volume["Attachments"][0]
                    ["InstanceId"]
                )
 
                instance_response=(
                    ec2.describe_instances(
                        InstanceIds=[
                            attached_instance_id
                        ]
                    )
                )
 
                reservations=(
                    instance_response[
                        "Reservations"
                    ]
                )
 
                if reservations:
 
                    instance=(
                        reservations[0]
                        ["Instances"][0]
                    )
 
                    if "Tags" in instance:
 
                        for tag in (
                            instance["Tags"]
                        ):
 
                            if (
                                tag["Key"]
                                =="Name"
                            ):
 
                                attached_instance_name=(
                                    tag["Value"]
                                )
 
            volumes.append({
 
                "volume_name":
                volume_name,
 
                "volume_id":
                volume["VolumeId"],
 
                "size_gb":
                volume["Size"],
 
                "state":
                volume["State"],
 
                "volume_type":
                volume["VolumeType"],
 
                "availability_zone":
                volume[
                    "AvailabilityZone"
                ],
 
                "attached_instance_name":
                attached_instance_name,
 
                "attached_instance_id":
                attached_instance_id
            })
 
        end_time=time.time()
 
        return {
 
            "count":
            len(volumes),
 
            "volumes":
            volumes,
 
            "time_taken_seconds":
            round(
                end_time-start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# CREATE EBS
# ==========================================================
 
@app.post("/storage/ebs/create")
 
def create_ebs_volume(
    req:CreateEBSRequest
):
 
    try:
 
        start_time=time.time()
 
        instance=(
            get_instance_by_name(
                req.instance_name
            )
        )
 
        if not instance:
 
            raise HTTPException(
                status_code=404,
                detail="Instance not found"
            )
 
        response=(
            ec2.create_volume(
 
                AvailabilityZone=
                instance[
                    "availability_zone"
                ],
 
                Size=req.size,
 
                VolumeType=
                req.volume_type,
 
                TagSpecifications=[
                    {
                        "ResourceType":
                        "volume",
 
                        "Tags":[
                            {
                                "Key":
                                "Name",
 
                                "Value":
                                req.tag_name
                            }
                        ]
                    }
                ]
            )
        )
 
        end_time=time.time()
 
        return {
 
            "message":
            "EBS volume created successfully",
 
            "volume_id":
            response["VolumeId"],
 
            "attached_instance_name":
            req.instance_name,
 
            "availability_zone":
            instance[
                "availability_zone"
            ],
 
            "size_gb":
            req.size,
 
            "volume_type":
            req.volume_type,
 
            "time_taken_seconds":
            round(
                end_time-start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================

# ATTACH EBS + AUTO MOUNT

# ==========================================================
 
@app.post("/storage/ebs/attach")
 
def attach_ebs_volume(

    req: AttachEBSRequest

):
 
    try:
 
        start_time = time.time()
 
        instance = get_instance_by_name(

            req.instance_name

        )
 
        if not instance:
 
            raise HTTPException(

                status_code=404,

                detail="Instance not found"

            )
 
        instance_id = instance["instance_id"]
 
        # --------------------------------------------------

        # ATTACH VOLUME

        # --------------------------------------------------
 
        ec2.attach_volume(
 
            VolumeId=req.volume_id,
 
            InstanceId=instance_id,
 
            Device="/dev/sdf"

        )
 
        # --------------------------------------------------

        # WAIT UNTIL VOLUME IS ATTACHED

        # --------------------------------------------------
 
        waiter = ec2.get_waiter(

            'volume_in_use'

        )
 
        waiter.wait(

            VolumeIds=[req.volume_id]

        )
 
        # --------------------------------------------------

        # WAIT EXTRA TIME FOR OS TO DETECT DISK

        # --------------------------------------------------
 
        time.sleep(20)
 
        # --------------------------------------------------

        # SSM CLIENT

        # --------------------------------------------------
 
        ssm = boto3.client(

            "ssm",

            region_name="us-east-1"

        )
 
        # --------------------------------------------------

        # CHECK IF INSTANCE IS ONLINE IN SSM

        # --------------------------------------------------
 
        managed_instances = (

            ssm.describe_instance_information()

        )
 
        online = False
 
        for info in managed_instances[

            "InstanceInformationList"

        ]:
 
            if (

                info["InstanceId"]

                == instance_id

            ):
 
                if (

                    info["PingStatus"]

                    == "Online"

                ):
 
                    online = True
 
        if not online:
 
            return {
 
                "message":

                "EBS attached but SSM agent is offline",
 
                "volume_id":

                req.volume_id,
 
                "instance_id":

                instance_id,
 
                "solution":

                "Start EC2 instance and ensure SSM agent is running"

            }
 
        # --------------------------------------------------

        # AUTO MOUNT COMMANDS

        # --------------------------------------------------
 
        commands = [
 
            "sudo mkdir -p /data",
 
            "sudo file -s /dev/xvdf",
 
            """

            if ! sudo blkid /dev/xvdf; then

                sudo mkfs -t ext4 /dev/xvdf

            fi

            """,
 
            "sudo mount /dev/xvdf /data || true",
 
            "sudo chmod -R 777 /data",
 
            "ls /data"

        ]
 
        command_response = ssm.send_command(
 
            InstanceIds=[instance_id],
 
            DocumentName="AWS-RunShellScript",
 
            Parameters={

                "commands": commands

            }

        )
 
        end_time = time.time()
 
        return {
 
            "message":

            "EBS attached and mounted successfully",
 
            "instance_name":

            req.instance_name,
 
            "instance_id":

            instance_id,
 
            "volume_id":

            req.volume_id,
 
            "device_name":

            "/dev/sdf",
 
            "command_id":

            command_response["Command"]["CommandId"],
 
            "time_taken_seconds":

            round(

                end_time - start_time,

                2

            )

        }
 
    except ClientError as e:
 
        raise HTTPException(

            status_code=400,

            detail=str(e)

        )
 
 
# ==========================================================
# DETACH REQUEST MODEL
# ==========================================================

class DetachEBSRequest(BaseModel):

    instance_name: str

    volume_id: str
 
# ==========================================================

# DETACH EBS + UNMOUNT CLEANLY

# ==========================================================
 
@app.post("/storage/ebs/detach")
 
def detach_ebs_volume(

    req: DetachEBSRequest

):
 
    try:
 
        start_time = time.time()
 
        instance = get_instance_by_name(

            req.instance_name

        )
 
        if not instance:
 
            raise HTTPException(

                status_code=404,

                detail="Instance not found"

            )
 
        instance_id = instance["instance_id"]
 
        # --------------------------------------------------

        # SSM CLIENT

        # --------------------------------------------------
 
        ssm = boto3.client(

            "ssm",

            region_name="us-east-1"

        )
 
        # --------------------------------------------------

        # CHECK INSTANCE ONLINE

        # --------------------------------------------------
 
        managed_instances = (

            ssm.describe_instance_information()

        )
 
        online = False
 
        for info in managed_instances[

            "InstanceInformationList"

        ]:
 
            if (

                info["InstanceId"]

                == instance_id

            ):
 
                if (

                    info["PingStatus"]

                    == "Online"

                ):
 
                    online = True
 
        # --------------------------------------------------

        # UNMOUNT BEFORE DETACH

        # --------------------------------------------------
 
        if online:
 
            commands = [
 
                "sudo sync",
 
                "sudo umount /data || true",
 
                "sudo rm -rf /data/lost+found || true",
 
                "lsblk"

            ]
 
            ssm.send_command(
 
                InstanceIds=[instance_id],
 
                DocumentName="AWS-RunShellScript",
 
                Parameters={

                    "commands": commands

                }

            )
 
            # Give time for unmount

            time.sleep(10)
 
        # --------------------------------------------------

        # DETACH EBS

        # --------------------------------------------------
 
        ec2.detach_volume(
 
            VolumeId=req.volume_id,
 
            InstanceId=instance_id,
 
            Force=False

        )
 
        # --------------------------------------------------

        # WAIT UNTIL AVAILABLE

        # --------------------------------------------------
 
        waiter = ec2.get_waiter(

            'volume_available'

        )
 
        waiter.wait(

            VolumeIds=[req.volume_id]

        )
 
        end_time = time.time()
 
        return {
 
            "message":

            "EBS detached successfully",
 
            "instance_name":

            req.instance_name,
 
            "instance_id":

            instance_id,
 
            "volume_id":

            req.volume_id,
 
            "time_taken_seconds":

            round(

                end_time - start_time,

                2

            )

        }
 
    except ClientError as e:
 
        raise HTTPException(

            status_code=400,

            detail=str(e)

        )
 
 
 
 
# ==========================================================
# MODIFY EBS
# ==========================================================
 
@app.put(
"/storage/ebs/modify/{volume_id}"
)
 
def modify_ebs_volume(
    volume_id:str,
    req:ModifyEBSRequest
):
 
    try:
 
        start_time=time.time()
 
        ec2.modify_volume(
 
            VolumeId=
            volume_id,
 
            Size=
            req.volume_size
        )
 
        end_time=time.time()
 
        return {
 
            "message":
            "EBS modified successfully",
 
            "volume_id":
            volume_id,
 
            "new_size_gb":
            req.volume_size,
 
            "time_taken_seconds":
            round(
                end_time-start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# DELETE EBS
# ==========================================================
 
@app.delete(
"/storage/ebs/delete/{volume_id}"
)
 
def delete_ebs_volume(
    volume_id:str
):
 
    try:
 
        start_time=time.time()
 
        ec2.delete_volume(
            VolumeId=volume_id
        )
 
        end_time=time.time()
 
        return {
 
            "message":
            "EBS deleted successfully",
 
            "volume_id":
            volume_id,
 
            "time_taken_seconds":
            round(
                end_time-start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
# ==========================================================

# WRITE DATA INTO EBS

# ==========================================================
 
class WriteDataRequest(BaseModel):
 
    instance_name: str
 
    volume_id: str
 
    file_name: str = "test.txt"
 
    content: str = "Hello from EBS"
 
 
@app.post("/storage/ebs/write-data")
 
def write_data_to_ebs(req: WriteDataRequest):
 
    try:
 
        start_time = time.time()
 
        # --------------------------------------------------

        # FIND INSTANCE

        # --------------------------------------------------
 
        instance = get_instance_by_name(

            req.instance_name

        )
 
        if not instance:
 
            raise HTTPException(

                status_code=404,

                detail="Instance not found"

            )
 
        instance_id = instance["instance_id"]
 
        # --------------------------------------------------

        # CHECK INSTANCE STATE

        # --------------------------------------------------
 
        instance_info = ec2.describe_instances(

            InstanceIds=[instance_id]

        )
 
        state = (

            instance_info["Reservations"][0]

            ["Instances"][0]["State"]["Name"]

        )
 
        if state != "running":
 
            raise HTTPException(

                status_code=400,

                detail=f"Instance is {state}. Must be running."

            )
 
        # --------------------------------------------------

        # WAIT BEFORE SSM COMMAND

        # --------------------------------------------------
 
        time.sleep(15)
 
        # --------------------------------------------------

        # CREATE SSM CLIENT

        # --------------------------------------------------
 
        ssm = boto3.client(

            "ssm",

            region_name="us-east-1"

        )
 
        # --------------------------------------------------

        # CHECK SSM STATUS

        # --------------------------------------------------
 
        managed_instances = ssm.describe_instance_information()
 
        managed_instance_ids = [
 
            i["InstanceId"]
 
            for i in managed_instances[

                "InstanceInformationList"

            ]

        ]
 
        if instance_id not in managed_instance_ids:
 
            raise HTTPException(

                status_code=400,

                detail=(

                    "Instance is not managed by SSM. "

                    "Check IAM role and SSM Agent."

                )

            )
 
        # --------------------------------------------------

        # WRITE DATA

        # --------------------------------------------------
 
        commands = [
 
            "sudo mkdir -p /data",
 
            "sudo mount /dev/xvdf /data || true",
 
            f'echo "{req.content}" | sudo tee /data/{req.file_name}',
 
            f"cat /data/{req.file_name}"

        ]
 
        command_response = ssm.send_command(
 
            InstanceIds=[instance_id],
 
            DocumentName="AWS-RunShellScript",
 
            Parameters={

                "commands": commands

            }

        )
 
        end_time = time.time()
 
        return {
 
            "message":

            "Data written successfully",
 
            "instance_name":

            req.instance_name,
 
            "instance_id":

            instance_id,
 
            "volume_id":

            req.volume_id,
 
            "file_name":

            req.file_name,
 
            "content":

            req.content,
 
            "command_id":

            command_response["Command"]["CommandId"],
 
            "time_taken_seconds":

            round(

                end_time - start_time,

                2

            )

        }
 
    except Exception as e:
 
        raise HTTPException(

            status_code=400,

            detail=str(e)

        )
 
 
# ==========================================================
# LIST ALL BUCKETS
# ==========================================================
 
@app.get("/buckets")
def list_buckets(request: Request):
    require_login(request) 
    try:
 
        start_time = time.time()
 
        response = s3.list_buckets()
 
        buckets = []
 
        for bucket in response.get("Buckets", []):
 
            buckets.append({
                "bucket_name": bucket["Name"],
                "created_at": str(
                    bucket["CreationDate"]
                )
            })
 
        end_time = time.time()
 
        return {
            "count": len(buckets),
            "buckets": buckets,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

 
 
# ==========================================================
# VIEW SINGLE BUCKET
# ==========================================================
 
@app.get("/bucket/{bucket_name}")
def view_bucket(
    bucket_name: str
):
 
    try:
 
        start_time = time.time()
 
        response = s3.list_objects_v2(
            Bucket=bucket_name
        )
 
        total_files = response.get(
            "KeyCount",
            0
        )
 
        end_time = time.time()
 
        return {
            "bucket_name": bucket_name,
            "total_files": total_files,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )# ==========================================================
# CREATE BUCKET
# ==========================================================
 
@app.post("/create-bucket")
def create_bucket(req: CreateBucketRequest, request: Request):
    require_login(request)
    try:
 
        start_time = time.time()
 
        s3.create_bucket(
            Bucket=req.bucket_name
        )
 
        end_time = time.time()
 
        return {
            "message": "Bucket created successfully",
            "bucket_name": req.bucket_name,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# UPLOAD FILE
# ==========================================================
 
@app.post("/upload-file")
async def upload_file(
    bucket_name: str,
    file: UploadFile = File(...)
):
 
    try:
 
        start_time = time.time()
 
        s3.upload_fileobj(
            file.file,
            bucket_name,
            file.filename
        )
 
        end_time = time.time()
 
        return {
            "message": "File uploaded successfully",
            "bucket_name": bucket_name,
            "file_name": file.filename,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# LIST FILES IN BUCKET
# ==========================================================
 
@app.get("/files/{bucket_name}")
def list_files(
    bucket_name: str
):
 
    try:
 
        start_time = time.time()
 
        response = s3.list_objects_v2(
            Bucket=bucket_name
        )
 
        files = []
 
        if "Contents" in response:
 
            for obj in response["Contents"]:
 
                files.append({
                    "file_name": obj["Key"],
                    "size_bytes": obj["Size"]
                })
 
        end_time = time.time()
 
        return {
            "bucket_name": bucket_name,
            "count": len(files),
            "files": files,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# DELETE FILE
# ==========================================================
 
@app.delete("/delete-file")
def delete_file(
    bucket_name: str,
    file_name: str
):
 
    try:
 
        start_time = time.time()
 
        s3.delete_object(
            Bucket=bucket_name,
            Key=file_name
        )
 
        end_time = time.time()
 
        return {
            "message": "File deleted successfully",
            "bucket_name": bucket_name,
            "file_name": file_name,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 
 
# ==========================================================
# DELETE BUCKET (AUTO EMPTY + DELETE)
# ==========================================================
 
@app.delete("/delete-bucket/{bucket_name}")
def delete_bucket(bucket_name: str):
 
    try:
 
        start_time = time.time()
 
        # ==========================================================
        # CHECK FILES INSIDE BUCKET
        # ==========================================================
 
        response = s3.list_objects_v2(
            Bucket=bucket_name
        )
 
        # ==========================================================
        # DELETE ALL FILES IF PRESENT
        # ==========================================================
 
        if "Contents" in response:
 
            objects_to_delete = []
 
            for obj in response["Contents"]:
 
                objects_to_delete.append({
                    "Key": obj["Key"]
                })
 
            s3.delete_objects(
                Bucket=bucket_name,
                Delete={
                    "Objects": objects_to_delete
                }
            )
 
        # ==========================================================
        # DELETE BUCKET
        # ==========================================================
 
        s3.delete_bucket(
            Bucket=bucket_name
        )
 
        end_time = time.time()
 
        return {
            "message": "Bucket and all files deleted successfully",
            "bucket_name": bucket_name,
            "time_taken_seconds": round(
                end_time - start_time,
                2
            )
        }
 
    except ClientError as e:
 
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
 

