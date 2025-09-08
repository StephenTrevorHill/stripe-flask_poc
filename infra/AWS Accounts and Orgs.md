# AWS Account Set-Up

## 2025-08-31 Created new account under my gmail address 
- Canadian Retail Tech Demos, Acct# 9972709131201 - this becomes the management account
- Created an organization - the management account
- set up control tower - this will set up a structure like this:
```
Root Organization
├── Security OU
│   ├── Log Archive Account (for centralized logging)
│   └── Audit Account (for security monitoring)
└── Root (your management account stays here)
```
or is it this?
```
Root Organization
├── Security OU
│   ├── Log Archive Account (centralized logging)
│   └── Audit Account (security monitoring)
└── Sandbox OU (ready for your projects)
```
control tower set up is running- it will create:
- Management account (your original)
- Security OU with Log Archive + Audit accounts
- Sandbox OU (ready for your projects)
- IAM Identity Center enabled

## 2025-09-01
control tower setup complete
Your AWS Organization
```
├── Management Account (your original account) = stephen.trevor.hill@gmail.com
├── Security OU
│   ├── Log Archive Account = stephen.trevor.hill+log.archive@gmail.com
│   └── Audit Account = stephen.trevor.hill+audit@gmail.com 
└── Sandbox OU (ready for your projects)
```

## New identity created using main email address
"IAM Identity Center creates a separate identity for accessing your multi-account environment. This gives you:
- 🔐 Single sign-on across all AWS accounts
- 🛡️ Better security than individual account passwords
- 📊 Centralized access management"
(not a new account - a new identity)
Access Portal URL: https://d-9066223c6f.awsapps.com/start 
Created an OU (organisational unit) for webhook demo "WebhookDemo"

to access the management account - sign on as root user
created a dev user under the additional dev gmail address

## CLI access
installed awscli
configured a cli sso profile for the extra developer
```
stripe_flask_poc > aws configure sso --profile webhook-dev

SSO session name (Recommended): webhook-dev
SSO start URL [None]: https://d-9066223c6f.awsapps.com/start/
SSO region [None]: us-east-1
SSO registration scopes [sso:account:access]:
Attempting to automatically open the SSO authorization page in your default browser.
If the browser does not open, open the following URL:

https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id=jGCPJ55YPjLyQKpAbihXN3VzLWVhc3QtMQ&redirect_uri=http%3A%2F%2F127.0.0.1%3A54408%2Foauth%2Fcallback&state=f4671304-4437-4eef-b640-fc0fe31b46d8&code_challenge_method=S256&scopes=sso%3Aaccount%3Aaccess&code_challenge=5cvDBFxGKZ-LakU1N9SIZSDxVBb3dOPShhSCXejrXeg
The only AWS account available to you is: 062250062530
Using the account ID 062250062530
The only role available to you is: DeveloperAccess
Using the role name "DeveloperAccess"
Default client Region [None]: us-east-1
CLI default output format (json if not specified) [None]:
To use this profile, specify the profile name using --profile, as shown:

aws sts get-caller-identity --profile webhook-dev
stripe_flask_poc > To use this profile, specify the profile name using --profile, as shown:

aws sts get-caller-identity --profile webhook-d 
stripe_flask_poc > aws sts get-caller-identity --profile webhook-dev
{
    "UserId": "AROAQ47TESLBLX4PRST62:stephen-developer",
    "Account": "062250062530",
    "Arn": "arn:aws:sts::062250062530:assumed-role/AWSReservedSSO_DeveloperAccess_91429f130505c1b0/stephen-developer"
}
stripe_flask_poc > 
```
```
Your Setup Summary
✅ CLI Profile: webhook-dev
✅ Account: WebhookDemo-Staging (062250062530)
✅ Permissions: DeveloperAccess
✅ Region: us-east-1
```

## Users, accounts, and orginzations
```
|── SSO Control Tower User
|       - user id = stephen.trevor.hill@gmail.com
|       - login via SSO portal at https://d-9066223c6f.awsapps.com/start/
├── Management Account (original account)
|       - Canadian Retail Tech Demos
|       - stephen.trevor.hill@gmail.com
|       - account id 972709131201
|       - access through the SSO OR
|       - sign on as a root user at https://console.aws.amazon.com/
├── Security OU
│   ├── Log Archive Account = stephen.trevor.hill+log.archive@gmail.com 
│   └── Audit Account = stephen.trevor.hill+audit@gmail.com 
└── Sandbox OU 
│   └── Project OU Webhook Demo
│       ├── Account WebhookDemo-Staging
│       |   └── User Identity for Developer Admin
|       |       - username = stephen-developer
|       |       - email = stephensoftware7@gmail.com
|       |       - password in password keeper
|       |       - MFA set up on Microsoft Authenticator
|       |       - set up in AWS CLI profile webhook-dev
|       |       - login via SSO @ https://d-9066223c6f.awsapps.com/start/
│       └── Stephen-Webhook-Prod 
│   ├── 

```
