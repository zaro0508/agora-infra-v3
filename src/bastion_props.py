from aws_cdk import aws_ec2 as ec2
from typing import Optional, Sequence


class BastionProps:
    """
    Bastion host properties

    key_name: Name of an existing EC2 KeyPair to enable SSH access to the instance
    instance_type: The EC2 instance type
    ami_id: AMI ID of the base AMI
    block_devices: Optional block devices to override the base AMI settings
    """

    def __init__(
        self,
        key_name: str,
        instance_type: ec2.InstanceType,
        ami_id: str,
        block_devices: Optional[Sequence[ec2.BlockDevice]] = None,
    ) -> None:
        self.key_name = key_name
        self.instance_type = instance_type
        self.ami_id = ami_id
        if block_devices is None:
            self.block_devices = []
        else:
            self.block_devices = block_devices
