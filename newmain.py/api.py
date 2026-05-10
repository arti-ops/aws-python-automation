from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
import time
from botocore.exceptions import ClientError

app = FastAPI()

ec2 = boto3.client("ec2", region_name="us-east-1")


# =========================
# REQUEST MODEL (CREATE)
# =========================

class CreateInstanceRequest(BaseModel):
    ami_id: str
    instance_type: str
    key_name: str = None
    security_group_id: str = None
    instance_name: str = "MyInstance"
    volume_size: int = 8


# =========================
# LIST INSTANCES
# =========================

@app.get("/instances")
def list_instances():

    try:
        response = ec2.describe_instances()
        instances = []

        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):

                instances.append({
                    "instance_id": instance.get("InstanceId"),
                    "state": instance.get("State", {}).get("Name"),
                    "type": instance.get("InstanceType"),
                    "public_ip": instance.get("PublicIpAddress", "N/A"),
                    "private_ip": instance.get("PrivateIpAddress", "N/A")
                })

        return {
            "count": len(instances),
            "instances": instances
        }

    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# CREATE INSTANCE
# =========================

@app.post("/create")
def create_instance(req: CreateInstanceRequest):

    try:
        response = ec2.run_instances(
            ImageId=req.ami_id,
            InstanceType=req.instance_type,
            KeyName=req.key_name,
            SecurityGroupIds=[req.security_group_id] if req.security_group_id else [],
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

        instance_id = response["Instances"][0]["InstanceId"]

        return {
            "message": "Instance creation initiated",
            "instance_id": instance_id
        }

    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# START INSTANCE (with time)
# =========================

@app.post("/start/{instance_id}")
def start_instance(instance_id: str):

    try:
        start_time = time.time()

        ec2.start_instances(InstanceIds=[instance_id])

        end_time = time.time()

        return {
            "message": "Start request sent",
            "instance_id": instance_id,
            "time_taken_seconds": round(end_time - start_time, 2)
        }

    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# STOP INSTANCE (with time)
# =========================

@app.post("/stop/{instance_id}")
def stop_instance(instance_id: str):

    try:
        start_time = time.time()

        ec2.stop_instances(InstanceIds=[instance_id])

        end_time = time.time()

        return {
            "message": "Stop request sent",
            "instance_id": instance_id,
            "time_taken_seconds": round(end_time - start_time, 2)
        }

    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# TERMINATE INSTANCE (with time)
# =========================

@app.post("/terminate/{instance_id}")
def terminate_instance(instance_id: str):

    try:
        start_time = time.time()

        ec2.terminate_instances(InstanceIds=[instance_id])

        end_time = time.time()

        return {
            "message": "Terminate request sent",
            "instance_id": instance_id,
            "time_taken_seconds": round(end_time - start_time, 2)
        }

    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))