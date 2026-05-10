import boto3
from botocore.exceptions import ClientError

ec2 = boto3.client('ec2')


# =========================
# SELECT INSTANCE
# =========================

def select_instance():

    response = ec2.describe_instances()
    instances = []

    print("\n========= EC2 INSTANCES =========\n")

    count = 1

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            name = "N/A"
            if 'Tags' in instance:
                for tag in instance['Tags']:

                    if tag['Key'] == 'Name':
                        name = tag['Value']

            state = instance['State']['Name']
            print(f"{count}. {name} ({state})")
            instances.append(instance)

            count += 1

    choice = int(input("\nChoose instance number: "))
    return instances[choice - 1]


# =========================
# SHOW INSTANCE DETAILS
# =========================

def show_instances():

    selected = select_instance()
    name = "N/A"

    if 'Tags' in selected:

        for tag in selected['Tags']:
            if tag['Key'] == 'Name':
                name = tag['Value']

    print("\n========= INSTANCE DETAILS =========\n")

    print(f"Name          : {name}")
    print(f"Instance ID   : {selected['InstanceId']}")
    print(f"State         : {selected['State']['Name']}")
    print(f"Public IP     : {selected.get('PublicIpAddress', 'N/A')}")
    print(f"Private IP    : {selected.get('PrivateIpAddress', 'N/A')}")
    print(f"AMI ID        : {selected['ImageId']}")
    print(f"Instance Type : {selected['InstanceType']}")
    print(f"Key Pair      : {selected.get('KeyName', 'N/A')}")
    print(f"Launch Time   : {selected['LaunchTime']}")

    print("--------------------------------------")


# =========================
# START INSTANCE
# =========================

def start_instance():
    instance = select_instance()
    instance_id = instance['InstanceId']
    ec2.start_instances(InstanceIds=[instance_id])
    print(f"\nStarting instance {instance_id}...\n")


# =========================
# STOP INSTANCE
# =========================

def stop_instance():
    instance = select_instance()
    instance_id = instance['InstanceId']
    ec2.stop_instances(InstanceIds=[instance_id])
    print(f"\nStopping instance {instance_id}...\n")


# =========================
# TERMINATE INSTANCE
# =========================

def terminate_instance():
    instance = select_instance()
    instance_id = instance['InstanceId']
    ec2.terminate_instances(InstanceIds=[instance_id])
    print(f"\nTerminating instance {instance_id}...\n")


# =========================
# SELECT AMI
# =========================

def select_ami():

    print("\n========= AMI SELECTION =========\n")

    print("1. Enter Custom AMI ID")
    print("2. Use Existing Instance AMI")

    choice = input("\nChoose Option: ")

    # MANUAL AMI
    if choice == "1":
        ami_id = input("\nEnter AMI ID (ami-xxxx): ")
        return ami_id

    # CREATE AMI FIRST
    elif choice == "2":

        instance = select_instance()
        instance_id = instance['InstanceId']
        ami_name = input("\nEnter New AMI Name: ")

        response = ec2.create_image(
            InstanceId=instance_id,
            Name=ami_name,
            NoReboot=True
        )

        ami_id = response['ImageId']

        print(f"\nAMI Created Successfully!")
        print(f"AMI ID: {ami_id}")

        return ami_id

    else:

        print("Invalid Choice")
        return select_ami()


# =========================
# SELECT INSTANCE TYPE
# =========================

def select_instance_type():

    instance_types = [

        "t2.micro",
        "t2.small",
        "t2.medium",

        "t3.micro",
        "t3.small",
        "t3.medium",

        "t3a.micro",
        "t3a.small",

        "m5.large",
        "m5.xlarge",

        "c5.large",
        "c5.xlarge"
    ]

    print("\n========= INSTANCE TYPES =========\n")

    for i, instype in enumerate(instance_types, start=1):

        print(f"{i}. {instype}")

    choice = int(input("\nChoose Instance Type: "))

    return instance_types[choice - 1]


# =========================
# SELECT KEY PAIR
# =========================

def select_key_pair():

    response = ec2.describe_key_pairs()

    keypairs = response['KeyPairs']

    print("\n========= KEY PAIRS =========\n")

    for i, key in enumerate(keypairs, start=1):

        print(f"{i}. {key['KeyName']}")

    print(f"{len(keypairs)+1}. Create New Key Pair")

    choice = int(input("\nChoose Option: "))

    # EXISTING KEYPAIR
    if choice <= len(keypairs):

        return keypairs[choice - 1]['KeyName']

    # CREATE NEW KEYPAIR
    elif choice == len(keypairs) + 1:

        new_key_name = input("\nEnter New Key Pair Name: ")

        new_key = ec2.create_key_pair(KeyName=new_key_name)

        private_key = new_key['KeyMaterial']

        filename = f"{new_key_name}.pem"

        with open(filename, "w") as file:

            file.write(private_key)

        print(f"\nNew Key Pair Created!")
        print(f"PEM file saved as: {filename}")

        return new_key_name

    else:

        print("Invalid Choice")
        return select_key_pair()
    
# =========================
# SELECT SECURITY GROUP
# =========================

def select_security_group():

    response = ec2.describe_security_groups()
    groups = response['SecurityGroups']

    print("\n========= SECURITY GROUPS =========\n")

    for i, group in enumerate(groups, start=1):
        print(f"{i}. {group['GroupName']}")

    print(f"{len(groups)+1}. Create New Security Group")
    choice = int(input("\nChoose Option: "))

    # EXISTING SECURITY GROUP
    if choice <= len(groups):
        return groups[choice - 1]['GroupId']

    # CREATE NEW SECURITY GROUP
    elif choice == len(groups) + 1:
        group_name = input("\nEnter Security Group Name: ")
        description = input("Enter Description: ")
        response = ec2.create_security_group(
            GroupName=group_name,
            Description=description
        )

        group_id = response['GroupId']

        print(f"\nSecurity Group Created!")
        print(f"Group ID: {group_id}")

        # OPEN SSH PORT 22
        ec2.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print("SSH Port 22 Enabled")
        return group_id
    else:

        print("Invalid Choice")
        return select_security_group()



# =========================
# CREATE INSTANCE
# =========================

def create_instance():

    try:
        ami_id = select_ami()
        instance_type = select_instance_type()
        key_name = select_key_pair()
        security_group = select_security_group()
        instance_name = input("\nEnter Instance Name: ")
        volume_size = int(input("\nEnter Volume Size (GB): "))


        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group],
            MinCount=1,
            MaxCount=1,

            BlockDeviceMappings=[
                {
                    'DeviceName': '/dev/xvda',
                    'Ebs': {
                        'VolumeSize': volume_size,                      
                    }
                }
            ],

            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': instance_name
                        }
                    ]
                }
            ]
        )

        instance_id = response['Instances'][0]['InstanceId']

        print(f"\nInstance Created Successfully!")
        print(f"Instance ID: {instance_id}")

    except ClientError as e:

        print("\nAWS ERROR:")
        print(e)


# =========================
# CREATE AMI
# =========================

def create_ami():
    instance = select_instance()
    instance_id = instance['InstanceId']
    ami_name = input("\nEnter AMI Name: ")

    response = ec2.create_image(
        InstanceId=instance_id,
        Name=ami_name,
        NoReboot=True
    )

    ami_id = response['ImageId']

    print(f"\nAMI Created Successfully!")
    print(f"AMI ID: {ami_id}")


# =========================
# MAIN MENU
# =========================

while True:

    print("""
========= AWS PYTHON MENU =========

1. Show Instance Details
2. Start Instance
3. Stop Instance
4. Terminate Instance
5. Create Instance
6. Create AMI
7. Exit

===================================

""")

    choice = input("Enter your choice: ")

    if choice == "1":
        show_instances()

    elif choice == "2":
        start_instance()

    elif choice == "3":
        stop_instance()

    elif choice == "4":
        terminate_instance()

    elif choice == "5":
        create_instance()

    elif choice == "6":
        create_ami()

    elif choice == "7":
        print("\nExiting Program...\n")
        break

    else:
        print("\nInvalid Choice\n")