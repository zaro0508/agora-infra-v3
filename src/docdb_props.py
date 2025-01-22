from aws_cdk import aws_ec2 as ec2


class DocdbProps:
    """
    DocumentDB properties

    instance_type: What type of instance to start for the replicas
    master_username: The database admin account username
    """

    def __init__(self, instance_type: ec2.InstanceType, master_username: str) -> None:
        self.instance_type = instance_type
        self.master_username = master_username
