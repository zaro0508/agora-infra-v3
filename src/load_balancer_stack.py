import aws_cdk as cdk

from aws_cdk import (
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_wafv2 as wafv2
)

from constructs import Construct


class LoadBalancerStack(cdk.Stack):
    """
    Load Balancer to allow access to ECS app from the internet
    """

    def __init__(
        self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.alb = elbv2.ApplicationLoadBalancer(
            self, "AppLoadBalancer", vpc=vpc, internet_facing=True
        )

        # WAF to protect against common web attacks (OWASP Top 10)
        web_acl = wafv2.CfnWebACL(self,"WebAcl",
            name="AppWebAcl",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(
                allow=wafv2.CfnWebACL.AllowActionProperty()
            ),
            scope="REGIONAL",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="AWSManagedRulesCommonRuleSet",
                sampled_requests_enabled=True
            ),
            rules=[wafv2.CfnWebACL.RuleProperty(
                name="AWSManagedRulesCommonRuleSet",
                priority=0,
                statement=wafv2.CfnWebACL.StatementProperty(
                    managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                        name="AWSManagedRulesCommonRuleSet",
                        vendor_name="AWS",
                        excluded_rules=[]
                    )
                ),
                action=wafv2.CfnWebACL.RuleActionProperty(
                    block={}
                ),
                visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                    cloud_watch_metrics_enabled=True,
                    metric_name="AWSManagedRulesCommonRuleSet",
                    sampled_requests_enabled=True
                ),
                override_action=wafv2.CfnWebACL.OverrideActionProperty(
                    none={}
                )
            )]

        )

        wafv2.CfnWebACLAssociation(
            self, "web_acl_association",
            resource_arn=self.alb.load_balancer_arn,
            web_acl_arn=web_acl.attr_arn
        )

        cdk.CfnOutput(
            self,
            "LoadBalancerDns",
            value=self.alb.load_balancer_dns_name,
            export_name=f"{construct_id}-dns",
        )
