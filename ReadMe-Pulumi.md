
# Air-tek Technical Assessment

## Prerequisites

1. [Install Pulumi](https://www.pulumi.com/docs/get-started/install/)
1. [Configure Pulumi for AWS](https://www.pulumi.com/docs/intro/cloud-providers/aws/setup/)
1. [Configure Pulumi for Python](https://www.pulumi.com/docs/intro/languages/python/)
1. [Install Docker](https://docs.docker.com/engine/installation/)

## Deploying and running the program

1. Create a new stack:

    ```bash
    $ pulumi stack init infra-stack
    ```

1. Set the AWS region:

    ```bash
    $ pulumi config set aws:region us-west-2
    ```

1. Run `pulumi up -y` to deploy changes:
    ```bash

         Type                                  Name                              Status              Info
     +   pulumi:pulumi:Stack                   infra-app-infra-app               created (167s)      
     +   ├─ docker:image:Image                 infra_api_image                   created (100s)      
     +   ├─ docker:image:Image                 infra_web_image                   created (100s)      
     +   ├─ aws:ec2:Vpc                        infra-app-vpc                     created (11s)       
     +   ├─ aws:ecs:Cluster                    infra-app-cluster                 created (10s)       
     +   ├─ aws:iam:Role                       infra-app-exec-role               created (1s)        
     +   ├─ aws:iam:Role                       infra-app-task-role               created (1s)        
     +   ├─ aws:ecr:Repository                 infra-app-ecr-repo                created (1s)        
     +   ├─ aws:ecr:LifecyclePolicy            infra-app-lifecycle-policy        created (0.25s)     
     +   ├─ aws:iam:RolePolicyAttachment       infra-app-exec-policy             created (0.53s)     
     +   ├─ aws:iam:RolePolicyAttachment       infra-app-access-policy           created (0.72s)     
     +   ├─ aws:ec2:InternetGateway            infra-app-gateway                 created (0.67s)     
     +   ├─ aws:ec2:Subnet                     infra-app-vpc-subnet              created (1s)        
     +   ├─ aws:lb:TargetGroup                 infra-api-targetgroup             created (1s)        
     +   ├─ aws:lb:TargetGroup                 infra-web-targetgroup             created (1s)        
     +   ├─ aws:ec2:SecurityGroup              security-group                    created (3s)        
     +   ├─ aws:ec2:RouteTable                 infra-app-routetable              created (1s)        
     +   ├─ aws:lb:LoadBalancer                infra-api-balancer                created (151s)      
     +   ├─ aws:lb:LoadBalancer                infra-web-balancer                created (151s)      
     +   ├─ aws:ec2:MainRouteTableAssociation  infra_app_routetable_association  created (0.61s)     
     +   ├─ aws:ecs:TaskDefinition             infra-api-task-definition         created (0.49s)     
     +   ├─ aws:lb:Listener                    infra-web-listener                created (0.56s)     
     +   ├─ aws:lb:Listener                    infra-api-listener                created (0.43s)     
     +   ├─ aws:ecs:TaskDefinition             infra-web-task-definition         created (0.64s)     
     +   ├─ aws:ecs:Service                    infra-api-service                 created (0.85s)     
     +   └─ aws:ecs:Service                    infra-web-service                 created (0.71s)     

    Outputs:
        infra-web-url: "infra-web-balancer-097b14a-03ff55706bf66faa.elb.us-east-2.amazonaws.com"

    Resources:
        + 26 created

    Duration: 3m39s
    ```

1. View the DNS address of the deployment via `stack output`:

    ```bash
    $ pulumi stack output
    Current stack outputs (1):
        OUTPUT         VALUE
        infra-web-url  infra-web-balancer-097b14a-03ff55706bf66faa.elb.us-east-2.amazonaws.com

    ```

1.  Verify that the deployment exists, by connecting to it in a browser window.

## Clean up

To clean up resources, run `pulumi destroy` and answer the confirmation question at the prompt.