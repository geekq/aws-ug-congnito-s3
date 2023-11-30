---
title: "AWS Lambda, Cognito, S3"
subtitle: In 3 days from idea to a working solution with AWS Lambda, Cognito, S3
author: "Vladimir Dobriakov"
institute: http://infrastructure-as-code.de
topic: "AWS User Group Cologne"
# theme: "Frankfurt"
theme: Madrid
# colortheme: "beaver"
fonttheme: "professionalfonts"
# mainfont: "Hack Nerd Font"
# fontsize: 10pt
fontsize: 13pt
# urlcolor: red
linkstyle: bold
aspectratio: 169
# titlegraphic: img/aleph0.png
# logo: img/aleph0-small.png
# date: 2023-11-30
date: 30.11.2023
mydate: AWS UG Cologne 2023-11-30
lang: de-DE
section-titles: false
toc: false
# header-includes:
#    - \usepackage{fancyhdr}
#    - \pagestyle{fancy}
#    - \fancyhead[L]{Your Company Name}
#    - \fancyfoot[C]{}
# To provide e.g. fancyhdr package:
# sudo apt-get install texlive
---

# Hello

## Cloud Computing

![Cloud Computing](img/Cloud_computing1.png)


## Glorified Data Center

![Cloud Computing](img/Cloud_computing2.png)


## Our Use Case - deliver CAD / CAM / MES software

![CAD CAM MES](img/CAD-CAM.jpg)


## No admin rights? Try Cloud9

![Cloud 9](img/cloud9.png)

## Technologies for Our Use Case

![PaaS](img/Cloud_computing3.png)



## OAuth2

![OAuth2 flow](img/OAuth2-Abstract-flow.png)


## Source Code

**Dive into Source Code**

## SAM Template -> CloudFormation Template

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  DownloadPortalFunction:
    Type: AWS::Serverless::Function
    DependsOn:
      - UserPool
      - UserPoolClient
    Properties:
      PackageType: Image
      Environment:
        Variables:
          USERPOOL_ID: !Ref UserPool
          CLIENT_ID: !Ref UserPoolClient
          CLIENT_SECRET: !Ref AppClientSecret
          LOGIN_DOMAIN: !Ref UserPoolDomain
          S3_BUCKET: !Ref S3DownloadBucket
      Events:
        HelloWorld:
          Type: Api
          Properties:
            Path: /download
            Method: get
```

## SAM Template - Lambda

```yaml
      Events:
        HelloWorld:
          Type: Api
          Properties:
            Path: /download
            Method: get
      Policies:
        - S3ReadPolicy:
            BucketName:
              !Ref S3DownloadBucket
    Metadata:
      Dockerfile: Dockerfile
      DockerContext: ./lambda_auth
      DockerTag: python3.9-v1
```

## Add your own resources, specific for your solution

```yaml
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      #UserPoolName: MyUserPool
      UsernameAttributes:
        - email
      Policies:
        PasswordPolicy:
          MinimumLength: 8
      Schema:
        - AttributeDataType: String
          Name: email
        - AttributeDataType: String
          Name: "Order_Number"
```

## Configure UserPool with OAuth

```
  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      CallbackURLs:
        - !Sub "https://${PortalURLPrefix}.execute-api.${AWS::Region}.amazonaws.com/Prod/download"
      # - !Sub "https://${ServerlessRestApi}.execute-api.${AWS::Region}.amazonaws.com"
      AllowedOAuthFlowsUserPoolClient: True
      GenerateSecret: True
      AllowedOAuthScopes:
        - email
        - openid
        - profile
      SupportedIdentityProviders:
        - COGNITO
      AllowedOAuthFlows:
        - code
        #- implicit
      UserPoolId: !Ref UserPool
      ExplicitAuthFlows:
        - ALLOW_USER_PASSWORD_AUTH
        - ALLOW_REFRESH_TOKEN_AUTH
```

## Add Users

Add known users including additional attributes like order number

```
Outputs:
  AddCognitoUser:
    Description: "Call to create cognito default user"
    Value: !Sub "aws cognito-idp admin-create-user --user-pool-id ${UserPool}
       --username max.mustermann@infrastructure-as-code.de
       --user-attributes Name=email,Value=max.mustermann@infrastructure-as-code.de
      Name=custom:CO_Number,Value=CO-0099999"
```

## S3 Bucket

```
  S3DownloadBucket:
    Type: AWS::S3::Bucket
    Properties:
      AccessControl: Private

Outputs:
  AddS3BucketContent:
    Value: !Sub "aws s3 cp licence.key s3://${S3DownloadBucket}/CO-005176/"

```


## Questions

**Questions ???**


## Bildnachweis

* Cloud_computing - Sam Johnston, CC BY-SA 3.0, via Wikimedia Commons
* CAD/CAM - Tebis Technische Informationssysteme AG, CC BY-SA 3.0, via Wikimedia Commons
* AWS cloud9 - screenshot AWS product description page
* OAuth 2.0 flow - Devansvd, CC-BY-SA-4.0, via Wikimedia Commons

