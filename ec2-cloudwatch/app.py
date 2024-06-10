#!/usr/bin/env python3
import aws_cdk as cdk

from aws_cdk import App
from ec2_cloudwatch.ec2_cloudwatch_stack import Ec2CloudwatchStack


app = App()

env = cdk.Environment(account="<your account id>", region="ap-southeast-1")

Ec2CloudwatchStack(app, "ec2-cloudwatch", env=env)
app.synth()
