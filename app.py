#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_web_servers.network_stack import NetworkStack
from cdk_web_servers.server_stack import ServerStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
)

# The network stack is created first; its VPC is passed to the server stack.
network = NetworkStack(app, "NetworkStack", env=env)
ServerStack(app, "ServerStack", vpc=network.vpc, env=env)

app.synth()
