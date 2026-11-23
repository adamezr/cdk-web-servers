from aws_cdk import Stack, CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_elasticloadbalancingv2_targets as targets
from constructs import Construct

# User data from the CloudFormation assignment (corpweb.json).
USER_DATA_COMMANDS = [
    "dnf update -y",
    "dnf install -y git httpd php",
    "service httpd start",
    "chkconfig httpd on",
    "aws s3 cp s3://seis665-public/index.php /var/www/html/",
]


class ServerStack(Stack):
    """Two web servers behind a load balancer, plus a MySQL database in the private subnets."""

    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.IVpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Web servers' security group: port 80 open from anywhere.
        web_sg = ec2.SecurityGroup(
            self,
            "WebServerSG",
            vpc=vpc,
            description="Web servers: HTTP from anywhere",
        )
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP from anywhere")

        # Instance role: SSM access (as in the lab) and read access to the web page in S3.
        instance_role = iam.Role(
            self,
            "WebInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )
        instance_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        )
        instance_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=["arn:aws:s3:::seis665-public/*"],
            )
        )

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(*USER_DATA_COMMANDS)

        # One web server in each public subnet.
        web_servers = []
        for index, subnet in enumerate(vpc.public_subnets, start=1):
            server = ec2.Instance(
                self,
                f"WebServer{index}",
                vpc=vpc,
                vpc_subnets=ec2.SubnetSelection(subnets=[subnet]),
                instance_type=ec2.InstanceType("t3.micro"),
                machine_image=ec2.MachineImage.latest_amazon_linux2023(),
                security_group=web_sg,
                role=instance_role,
                user_data=user_data,
            )
            web_servers.append(server)
            CfnOutput(self, f"WebServer{index}Id", value=server.instance_id)

        # Database security group: port 3306 only from the web servers' security group.
        db_sg = ec2.SecurityGroup(
            self,
            "DatabaseSG",
            vpc=vpc,
            description="MySQL: port 3306 from web servers only",
            allow_all_outbound=False,
        )
        db_sg.add_ingress_rule(web_sg, ec2.Port.tcp(3306), "MySQL from web servers")

        # RDS MySQL instance. Its subnet group contains all the private subnets.
        database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_4_7),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_sg],
            credentials=rds.Credentials.from_generated_secret("admin"),
            allocated_storage=20,
            storage_encrypted=True,
            multi_az=False,
            publicly_accessible=False,
            backup_retention=Duration.days(0),
            delete_automated_backups=True,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Load balancer that spreads requests across both web servers.
        load_balancer = elbv2.ApplicationLoadBalancer(
            self,
            "WebLoadBalancer",
            vpc=vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )
        # The load balancer's security group blocks outbound traffic by default,
        # so explicitly allow it to reach the web servers on port 80.
        load_balancer.connections.allow_to(web_sg, ec2.Port.tcp(80), "Load balancer to web servers")
        listener = load_balancer.add_listener("HttpListener", port=80, open=True)
        listener.add_targets(
            "WebServers",
            port=80,
            targets=[targets.InstanceTarget(server, 80) for server in web_servers],
            health_check=elbv2.HealthCheck(path="/index.php", healthy_http_codes="200"),
        )

        CfnOutput(self, "LoadBalancerUrl", value=f"http://{load_balancer.load_balancer_dns_name}/")
        CfnOutput(self, "DatabaseEndpoint", value=database.db_instance_endpoint_address)
        CfnOutput(self, "DatabaseSecretName", value=database.secret.secret_name)
        CfnOutput(self, "WebServerSecurityGroupId", value=web_sg.security_group_id)
        CfnOutput(self, "DatabaseSecurityGroupId", value=db_sg.security_group_id)
