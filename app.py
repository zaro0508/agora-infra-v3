from os import environ

import aws_cdk as cdk

from src.ecs_stack import EcsStack
from src.load_balancer_stack import LoadBalancerStack
from src.network_stack import NetworkStack
from src.service_props import ServiceProps, ContainerVolume, ServiceSecret
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
            "TAGS": {"CostCenter": "Agora / 112300"},
        }
    case "stage":
        environment_variables = {
            "VPC_CIDR": "10.254.173.0/24",
            "FQDN": "stage.agora.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:681175625864:certificate/69b3ba97-b382-4648-8f94-a250b77b4994",
            "TAGS": {"CostCenter": "Agora / 112300"},
        }
    case "dev":
        environment_variables = {
            "VPC_CIDR": "10.254.172.0/24",
            "FQDN": "dev.agora.io",
            "CERTIFICATE_ARN": "arn:aws:acm:us-east-1:607346494281:certificate/e8093404-7db1-4042-90d0-01eb5bde1ffc",
            "TAGS": {"CostCenter": "Agora / 112300"},
        }
    case _:
        valid_envs_str = ",".join(VALID_ENVIRONMENTS)
        raise SystemExit(
            f"Must set environment variable `ENV` to one of {valid_envs_str}. Currently set to {environment}."
        )

stack_name_prefix = f"agora-{environment}"
fully_qualified_domain_name = environment_variables["FQDN"]
environment_tags = environment_variables["TAGS"]
agora_version = "4.0.0-rc1"

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
    namespace=fully_qualified_domain_name,
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

api_props = ServiceProps(
    container_name="agora-api",
    container_location=f"ghcr.io/sage-bionetworks/agora-api:{agora_version}",
    container_port=3333,
    container_memory=1024,
    container_env_vars={
        "NODE_ENV": "development"
        "MONGODB_PORT": "27017",
        "MONGODB_NAME": "agora"
    },
    container_secrets=[
        ServiceSecret(
            secret_name=f"{stack_name_prefix}/MongodbUsername",
            environment_key="MONGODB_USER",
        ),
        ServiceSecret(
            secret_name=f"{stack_name_prefix}/MongodbPassword",
            environment_key="MONGODB_PASS",
        ),
        ServiceSecret(
            secret_name=f"{stack_name_prefix}/MongodbHost",
            environment_key="MONGODB_HOST",
        ),
    ]
)
api_stack = ServiceStack(
    scope=cdk_app,
    construct_id=f"{stack_name_prefix}-api",
    vpc=network_stack.vpc,
    cluster=ecs_stack.cluster,
    props=api_props,
)

app_props = ServiceProps(
    container_name="agora-app",
    container_location=f"ghcr.io/sage-bionetworks/agora-app:{agora_version}",
    container_port=4200,
    container_memory=200,
    container_env_vars={
        "API_DOCS_URL": f"http://{fully_qualified_domain_name}/api-docs",
        "APP_VERSION": f"{agora_version}",
        "CSR_API_URL": f"http://{fully_qualified_domain_name}/api/v1",
        "SSR_API_URL": "http://agora-api:3333/v1",
        "ROLLBAR_TOKEN"="e788198867474855a996485580b08d03"
        "TAG_NAME"=f"agora/v${agora_version}"
    },
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
    container_env_vars={
        "API_DOCS_HOST": "agora-api-docs",
        "API_DOCS_PORT": "8010",
        "API_HOST": "agora-api",
        "API_PORT": "3333",
        "APP_HOST": "agora-app",
        "APP_PORT": "4200",
    },
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
apex_stack.add_dependency(api_stack)

cdk_app.synth()
