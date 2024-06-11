from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_cloudwatch as cloudwatch,
    aws_backup as backup
)

from aws_cdk.aws_events import Rule, Schedule
from aws_cdk.aws_events_targets import AwsApi

from constructs import Construct

class Ec2CloudwatchStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC
        vpc = ec2.Vpc(self, "VPC", ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"))

        vpc.add_gateway_endpoint("S3Endpoint",
                                        service=ec2.GatewayVpcEndpointAwsService.S3,
                                        subnets=[
                                            ec2.SubnetSelection(
                                                subnet_type=ec2.SubnetType.PUBLIC
                                            )
                                        ]
                                    )
        
        # BastionServer
        bastion_server = ec2.BastionHostLinux(self, "BastionServer",
                                        vpc=vpc,
                                        subnet_selection=ec2.SubnetSelection(
                                            subnet_type=ec2.SubnetType.PUBLIC)
                                    )
        
        # Write your IP range to access this server instead of x.x.x.x/32
        bastion_server.allow_ssh_access_from(ec2.Peer.ipv4("163.116.207.136/32"))

        # OS
        amzn_linux_2023 = ec2.LookupMachineImage(
                                        name="al2023-ami-2*.0-kernel-6.1-x86_64",
                                        filters={
                                            "architecture": ["x86_64"],
                                            "owner-alias": ["amazon"],
                                            "state": ["available"],
                                            "virtualization-type": ["hvm"]
                                        }
        )


        # amzn_linux = ec2.MachineImage.latest_amazon_linux2(
        #                                 generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
        #                                 edition=ec2.AmazonLinuxEdition.STANDARD,
        #                                 virtualization=ec2.AmazonLinuxVirt.HVM,
        #                                 storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE
        #                             )
        
        # security group
        security_group = ec2.SecurityGroup(self, "SecurityGroup",
                                        vpc=vpc,
                                        description="SecurityGroup for CDKtest",
                                        security_group_name="saito-securitygroup",
                                        allow_all_outbound=True
                                    )
        
        security_group.add_ingress_rule(ec2.Peer.ipv4('10.0.0.0/16'),
                                        ec2.Port.tcp(22),
                                        "allow ssh access from VPC"
                                    )
        
        # WebServer
        web_server = ec2.Instance(self, "WebServer",
                                        instance_type=ec2.InstanceType("m5.large"),
                                        machine_image=amzn_linux_2023,
                                        vpc=vpc,
                                        vpc_subnets=ec2.SubnetSelection(
                                            subnet_type=ec2.SubnetType.PUBLIC),
                                        security_group=security_group,
                                        # key_pair="saito-keypairs"
                                    )
        
        # allow access port
        web_server.connections.allow_from_any_ipv4(ec2.Port.tcp(80), "allow http")
        web_server.connections.allow_from_any_ipv4(ec2.Port.tcp(443), "allow https")

        # Create a second EBS volume for WebServer
        web_server.instance.add_property_override("BlockDeviceMappings", [{
                                        "DeviceName": "/dev/sdb",
                                        "Ebs": {
                                            "VolumeSize": "30",
                                            "VolumeType": "gp3",
                                            "DeleteOnTermination": "true"
                                        }
                                    }])
        
        # Cloudwatch event rule to stop instances every day in 09:00 UTC
        stop_instanse = AwsApi(
                                        service="EC2",
                                        action="stopInstances",
                                        parameters={"InstanceIds": [
                                            web_server.instance_id,
                                            bastion_server.instance_id
                                        ]}
                                    )
        
        Rule(self, "ScheduleRule",
                                        schedule=Schedule.cron(
                                            minute="0",
                                            hour="15"
                                        ),
                                        targets=[stop_instanse]
                                    )
        
        # Backup
        vault = backup.BackupVault(self, "BackupVault",
                                   backup_vault_name="saito_backup_vault",
                                   removal_policy=RemovalPolicy.DESTROY
                                   )

        # Create AWS Backup Plan

        plan = backup.BackupPlan(self, "BackupPlan", backup_plan_name="saito_backupplan")

        plan.add_selection("Selection", resources=[
                                        backup.BackupResource.from_ec2_instance(web_server),
                                        backup.BackupResource.from_tag("Name", "BastionServer")
                                    ])
        
        plan.add_rule(backup.BackupPlanRule(
                                        backup_vault=vault,
                                        rule_name="saito_backup_rule",
                                        schedule_expression=Schedule.cron(
                                            minute="0",
                                            hour="16",
                                            day="1",
                                            month="1-12"
                                            ),
                                        delete_after=Duration.days(100),
                                        move_to_cold_storage_after=Duration.days(10)
                                    ))
        
        # Output parameters
        output = CfnOutput(self, "BationServer_parameters",
                                        value=bastion_server.instance_public_ip,
                                        description="BastionServer Public IP"
                                    )

        output = CfnOutput(self, "WebServer_parameters",
                                        value=web_server.instance_public_ip,
                                        description="WebServer Public IP"
                                    )
