"""A Python Pulumi program"""

import base64
import json

import pulumi
import pulumi_aws as aws
import pulumi_docker as docker

from pulumi_aws_tags import register_auto_tags

# Automatically inject tags to created AWS resources.
register_auto_tags(
    {"infra-app-tag": pulumi.get_project() + "-" + pulumi.get_stack()}
)

external_port = 80
infra_port = 5000

# The ECS cluster in which our application and databse will run
infra_app_cluster = aws.ecs.Cluster("infra-app-cluster")

# Creating a VPC and a public subnet
infra_app_vpc = aws.ec2.Vpc("infra-app-vpc",
    cidr_block="172.31.0.0/16",
    enable_dns_hostnames=True)

infra_app_vpc_subnet = aws.ec2.Subnet("infra-app-vpc-subnet",
    cidr_block="172.31.32.0/20",
    vpc_id=infra_app_vpc.id)

# Creating a gateway to the web for the VPC
infra_app_gateway = aws.ec2.InternetGateway("infra-app-gateway",
    vpc_id=infra_app_vpc.id)

infra_app_routetable = aws.ec2.RouteTable("infra-app-routetable",
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block="0.0.0.0/0",
            gateway_id=infra_app_gateway.id,
        )
    ],
    vpc_id=infra_app_vpc.id)

# Associating our gateway with our VPC, to allow our infra app to communicate with the greater internet
infra_app_routetable_association = aws.ec2.MainRouteTableAssociation("infra_app_routetable_association",
    route_table_id=infra_app_routetable.id,
    vpc_id=infra_app_vpc.id)

# Creating a Security Group that restricts incoming traffic to HTTP
infra_app_security_group = aws.ec2.SecurityGroup("security-group",
    vpc_id=infra_app_vpc.id,
    description="Enables HTTP access",
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        protocol='tcp',
        from_port=0,
        to_port=65535,
        cidr_blocks=['0.0.0.0/0'],
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol='-1',
        from_port=0,
        to_port=0,
        cidr_blocks=['0.0.0.0/0'],
    )])

# Creating an IAM role used by Fargate to execute all our services
infra_app_exec_role = aws.iam.Role("infra-app-exec-role",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
        {
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }]
    }""")

# Attaching execution permissions to the exec role
exec_policy_attachment = aws.iam.RolePolicyAttachment("infra-app-exec-policy", role=infra_app_exec_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy")

# Creating an IAM role used by Fargate to manage tasks
infra_app_task_role = aws.iam.Role("infra-app-task-role",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
        {
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }]
    }""")

# Attaching execution permissions to the task role
task_policy_attachment = aws.iam.RolePolicyAttachment("infra-app-access-policy", role=infra_app_task_role.name,
    policy_arn=aws.iam.ManagedPolicy.AMAZON_ECS_FULL_ACCESS)

# Creating storage space to upload a docker image of our infra app to
infra_app_ecr_repo = aws.ecr.Repository("infra-app-ecr-repo",
    image_tag_mutability="MUTABLE")

# Attaching an application life cycle policy to the storage
infra_app_lifecycle_policy = aws.ecr.LifecyclePolicy("infra-app-lifecycle-policy",
    repository=infra_app_ecr_repo.name,
    policy="""{
        "rules": [
            {
                "rulePriority": 10,
                "description": "Remove untagged images",
                "selection": {
                    "tagStatus": "untagged",
                    "countType": "imageCountMoreThan",
                    "countNumber": 1
                },
                "action": {
                    "type": "expire"
                }
            }
        ]
    }""")

# Creating a target group through which the infra api backend receives requests
infra_api_targetgroup = aws.lb.TargetGroup("infra-api-targetgroup",
    port=infra_port,
    protocol="TCP",
    target_type="ip",
    stickiness=aws.lb.TargetGroupStickinessArgs(
        enabled=False,
        type="source_ip",
    ),
    vpc_id=infra_app_vpc.id)

# Creating a load balancer to spread out incoming requests
infra_api_balancer = aws.lb.LoadBalancer("infra-api-balancer",
    load_balancer_type="network",
    internal=True,
    security_groups=[],
    subnets=[infra_app_vpc_subnet.id])

# Forwards internal traffic using the infra port to the infra api target group
infra_api_listener = aws.lb.Listener("infra-api-listener",
    load_balancer_arn=infra_api_balancer.arn,
    port=infra_port,
    protocol="TCP",
    default_actions=[aws.lb.ListenerDefaultActionArgs(
        type="forward",
        target_group_arn=infra_api_targetgroup.arn
    )])

# Creating a target group through which the infra web frontend receives requests
infra_web_targetgroup = aws.lb.TargetGroup("infra-web-targetgroup",
    port=external_port,
    protocol="TCP",
    target_type="ip",
    stickiness=aws.lb.TargetGroupStickinessArgs(
        enabled=False,
        type="source_ip",
    ),
    vpc_id=infra_app_vpc.id)

# Creating a load balancer to spread out incoming requests
infra_web_balancer = aws.lb.LoadBalancer("infra-web-balancer",
    load_balancer_type="network",
    internal=False,
    security_groups=[],
    subnets=[infra_app_vpc_subnet.id])

# Forwards public traffic using the external port to the infra web target group
infra_web_listener = aws.lb.Listener("infra-web-listener",
    load_balancer_arn=infra_web_balancer.arn,
    port=external_port,
    protocol="TCP",
    default_actions=[aws.lb.ListenerDefaultActionArgs(
        type="forward",
        target_group_arn=infra_web_targetgroup.arn
    )])

# Creating a Docker image from the Dockerfile, which we will use
# to upload our infra app
def get_registry_info(rid):
    creds = aws.ecr.get_credentials(registry_id=rid)
    decoded = base64.b64decode(creds.authorization_token).decode()
    parts = decoded.split(':')
    if len(parts) != 2:
        raise Exception("Invalid credentials")
    return docker.ImageRegistry(creds.proxy_endpoint, parts[0], parts[1])

infra_app_registry = infra_app_ecr_repo.registry_id.apply(get_registry_info)

infra_api_image = docker.Image("infra_api_image",
                        build=docker.DockerBuild(context=".", dockerfile="./infra-api/Dockerfile"),
                        image_name=infra_app_ecr_repo.repository_url,
                        skip_push=False,
                        registry=infra_app_registry,
)

# Creating a task definition for the infra api instance.
infra_api_task_definition = aws.ecs.TaskDefinition("infra-api-task-definition",
    family="infra-api-task-definition-family",
    cpu="256",
    memory="512",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    execution_role_arn=infra_app_exec_role.arn,
    task_role_arn=infra_app_task_role.arn,
    container_definitions=pulumi.Output.json_dumps([{
        "name": "infra-api-container",
        "image": infra_api_image.image_name,
        "memory": 512,
        "essential": True,
        "portMappings": [{
            "containerPort": infra_port,
            "hostPort": infra_port,
            "protocol": "tcp"
        }]
    }]))

# Launching our infra api service on Fargate, using our configurations and load balancers
infra_api_service = aws.ecs.Service("infra-api-service",
    cluster=infra_app_cluster.arn,
    desired_count=1,
    launch_type="FARGATE",
    task_definition=infra_api_task_definition.arn,
    wait_for_steady_state=False,
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        assign_public_ip=True,
        subnets=[infra_app_vpc_subnet.id],
        security_groups=[infra_app_security_group.id]
    ),
    load_balancers=[aws.ecs.ServiceLoadBalancerArgs(
        target_group_arn=infra_api_targetgroup.arn,
        container_name="infra-api-container",
        container_port=infra_port,
    )],
    opts=pulumi.ResourceOptions(depends_on=[infra_api_listener]),
)

infra_api_endpoint = {"url": pulumi.Output.concat(
    'http://', infra_api_balancer.dns_name, ':', str(infra_port), '/WeatherForecast')}

infra_web_image = docker.Image("infra_web_image",
                        build=docker.DockerBuild(context=".", dockerfile="./infra-web/Dockerfile"),
                        image_name=infra_app_ecr_repo.repository_url,
                        skip_push=False,
                        registry=infra_app_registry,
)

# Creating a task definition for the infra web instance.
infra_web_task_definition = aws.ecs.TaskDefinition("infra-web-task-definition",
    family="infra-web-task-definition-family",
    cpu="256",
    memory="512",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    execution_role_arn=infra_app_exec_role.arn,
    task_role_arn=infra_app_task_role.arn,
    container_definitions=pulumi.Output.json_dumps([{
        "name": "infra-web-container",
        "image": infra_web_image.image_name,
        "memory": 512,
        "essential": True,
        "portMappings": [{
            "containerPort": infra_port,
            "hostPort": infra_port,
            "protocol": "tcp"
        }],
        "environment": [
            { "name": "ApiAddress", "value": infra_api_endpoint["url"] },
        ],
    }]))

# Launching our infra web service on Fargate, using our configurations and load balancers
infra_web_service = aws.ecs.Service("infra-web-service",
    cluster=infra_app_cluster.arn,
    desired_count=1,
    launch_type="FARGATE",
    task_definition=infra_web_task_definition.arn,
    wait_for_steady_state=False,
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        assign_public_ip=True,
        subnets=[infra_app_vpc_subnet.id],
        security_groups=[infra_app_security_group.id]
    ),
    load_balancers=[aws.ecs.ServiceLoadBalancerArgs(
        target_group_arn=infra_web_targetgroup.arn,
        container_name="infra-web-container",
        container_port=infra_port,
    )],
    opts=pulumi.ResourceOptions(depends_on=[infra_api_service, infra_web_listener]),
)

# Exporting the url of our infra api.
# pulumi.export("infra-api-url", infra_api_balancer.dns_name)

# Exporting the url of our infra web.
pulumi.export("infra-web-url", infra_web_balancer.dns_name)
