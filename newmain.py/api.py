from fastapi import FastAPI
import boto3

app = FastAPI()

ec2 = boto3.client("ec2", region_name="us-east-1")

@app.get("/instances")
def list_instances():
    response = ec2.describe_instances()

    instances = []

    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            instances.append({
                "InstanceId": instance["InstanceId"],
                "State": instance["State"]["Name"],
                "Type": instance["InstanceType"]
            })

    return {"instances": instances}

@app.post("/start/{instance_id}")
def start(instance_id: str):
    try:
        response = ec2.start_instances(InstanceIds=[instance_id])
        return {"message": "Starting instance", "response": response}
    except Exception as e:
        return {"error": str(e)}

@app.post("/stop/{instance_id}")
def stop_instance(instance_id: str):
    ec2.stop_instances(InstanceIds=[instance_id])
    return {"message": f"Stopping {instance_id}"}