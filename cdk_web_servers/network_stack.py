from aws_cdk import Stack, CfnOutput
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):
    """VPC with one public and one private subnet in each of two Availability Zones."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # CDK creates and attaches the internet gateway for the public subnets.
        # The private subnets have no internet route (no NAT gateway), which keeps
        # the database unreachable from the internet and avoids NAT gateway charges.
        self._vpc = ec2.Vpc(
            self,
            "WebVpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        CfnOutput(self, "VpcId", value=self._vpc.vpc_id)

    # Getter so other stacks can use this VPC (cross-stack resource sharing).
    @property
    def vpc(self) -> ec2.Vpc:
        return self._vpc
