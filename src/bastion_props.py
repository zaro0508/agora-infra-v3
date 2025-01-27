from aws_cdk import aws_ec2 as ec2


class BastionProps:
    """
    Bastion host properties

    key_name: Name of an existing EC2 KeyPair to enable SSH access to the instance
    instance_type: The EC2 instance type
    ami_id: ID of the AMI to deploy
    ami_region: Region of the AMI to deploy
    """

    def __init__(
        self,
        key_name: str,
        instance_type: ec2.InstanceType,
        ami_id: str,
        ami_region: str,
    ) -> None:
        self.key_name = key_name
        self.instance_type = instance_type
        self.ami_id = ami_id
        self.ami_region = ami_region
