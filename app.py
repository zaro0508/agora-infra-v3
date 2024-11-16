from os import environ

import aws_cdk as cdk

from src.ecs_stack import EcsStack
from src.load_balancer_stack import LoadBalancerStack
from src.network_stack import NetworkStack
from src.service_props import ServiceProps, ContainerVolume
from src.service_stack import LoadBalancedServiceStack, ServiceStack

# get the environment and set environment specific variables
VALID_ENVIRONMENTS = ["dev", "stage", "prod"]
environment = environ.get("ENV")
match environment:
    case "prod":
        environment_variables = {
            "VPC_CIDR": "10.254.174.0/24",
            "FQDN": "prod.agora.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:681175625864:certificate/69b3ba97-b382-4648-8f94-a250b77b4994",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case "stage":
        environment_variables = {
            "VPC_CIDR": "10.254.173.0/24",
            "FQDN": "stage.agora.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:681175625864:certificate/69b3ba97-b382-4648-8f94-a250b77b4994",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case "dev":
        environment_variables = {
            "VPC_CIDR": "10.254.172.0/24",
            "FQDN": "dev.agora.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:607346494281:certificate/e8093404-7db1-4042-90d0-01eb5bde1ffc",
            "TAGS": {"CostCenter": "NO PROGRAM / 000000"},
        }
    case _:
        valid_envs_str = ",".join(VALID_ENVIRONMENTS)
        raise SystemExit(
            f"Must set environment variable `ENV` to one of {valid_envs_str}. Currently set to {environment}."
        )

stack_name_prefix = f"agora-{environment}"
environment_tags = environment_variables["TAGS"]
agora_version = "0.0.2"

# Define stacks
cdk_app = cdk.App()

# recursively apply tags to all stack resources
if environment_tags:
    for key, value in environment_tags.items():
        cdk.Tags.of(cdk_app).add(key, value)

network_stack = NetworkStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-network",
    vpc_cidr=environment_variables["VPC_CIDR"],
)

ecs_stack = EcsStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-ecs",
    vpc=network_stack.vpc,
    namespace=environment_variables["FQDN"],
)

# From AWS docs https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-connect-concepts-deploy.html
# The public discovery and reachability should be created last by AWS CloudFormation, including the frontend
# client service. The services need to be created in this order to prevent an time period when the frontend
# client service is running and available the public, but a backend isn't.
load_balancer_stack = LoadBalancerStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-load-balancer",
    vpc=network_stack.vpc,
)

api_docs_props = ServiceProps(
    container_name="agora-api-docs",
    container_location=f"ghcr.io/sage-bionetworks/agora-api-docs:{agora_version}",
    container_port=8010,
    container_memory=200,
)
api_docs_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-api-docs",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=api_docs_props,
)

mongo_props = ServiceProps(
    container_name="agora-mongo",
    container_location=f"ghcr.io/sage-bionetworks/agora-mongo:{agora_version}",
    container_port=27017,
    container_memory=500,
    container_env_vars={
        "MONGO_INITDB_ROOT_USERNAME": "root",
        "MONGO_INITDB_ROOT_PASSWORD": "changeme",
        "MONGO_INITDB_DATABASE": "agora",
    },
    container_volumes=[
        ContainerVolume(
            path="/data/db",
            size=30,
        )
    ],
)
mongo_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-mongo",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=mongo_props,
)

# It is probably not appropriate host this container in ECS
# data_props = ServiceProps(
#     container_name="agora-data",
#     container_location=f"ghcr.io/sage-bionetworks/agora-data:{agora_version}",
#     container_port=9999,       # Not used
#     container_memory=2048,
# )
# data_stack = ServiceStack(
#     scope=cdk_app,
#     construct_id=f"{stack_name_prefix}-data",
#     vpc=network_stack.vpc,
#     cluster=ecs_stack.cluster,
#     props=data_props,
# )
# data_stack.add_dependency(mongo_stack)

api_props = ServiceProps(
    container_name="agora-api",
    container_location=f"ghcr.io/sage-bionetworks/agora-data:{agora_version}",
    container_port=3333,
    container_memory=1024,
)
api_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-api",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=api_props,
)
api_stack.add_dependency(mongo_stack)

app_props = ServiceProps(
    container_name="agora-app",
    container_location=f"ghcr.io/sage-bionetworks/agora-app:{agora_version}",
    container_port=4200,
    container_memory=200,
)
app_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-app",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=app_props,
)
app_stack.add_dependency(api_stack)

apex_props = ServiceProps(
    container_name="agora-apex",
    container_location=f"ghcr.io/sage-bionetworks/agora-apex:{agora_version}",
    container_port=80,
    container_memory=200,
)
apex_stack = LoadBalancedServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-apex",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=apex_props,
    load_balancer=load_balancer_stack.alb,
    certificate_arn=environment_variables["CERTIFICATE_ARN"],
    health_check_path="/health",
)
apex_stack.add_dependency(app_stack)
apex_stack.add_dependency(api_docs_stack)
apex_stack.add_dependency(api_stack)

cdk_app.synth()
