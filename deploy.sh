#!/bin/bash
#Suggest deploying to us-east-1 due to SES
export AWS_DEFAULT_REGION=us-east-1 
#Change the below, an s3 bucket to store lambda code for deploy, and store configuration file
#Must be in same region as lambda (ie AWS_DEFAULT_REGION)
export CONFIG_BUCKET=changeme
export CONFIG_FILE=config.yaml
#Change below to set the save bucket for saving site fingerprint data.
export BUCKET=changeme

if [ ! -f bin/lambda.zip ]; then
    echo "lambda.zip not found! Run build.sh first."
    exit 1
fi

cd src
zip -ur ../bin/lambda.zip lambda_module.py AWSHelper.py config.yaml log_config.yaml test11.htm test20.htm
cd ..
aws cloudformation package \
   --template-file src/sam.yaml \
   --output-template-file deploy.sam.yaml \
   --s3-bucket $CONFIG_BUCKET \
   --s3-prefix automate-aurora-new-version-checking-build
aws cloudformation deploy \
  --template-file deploy.sam.yaml \
  --stack-name automate-aurora-new-version-checking-build  \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides CONFIGBUCKET=$CONFIG_BUCKET CONFIGFILE=$CONFIG_FILE BUCKET=$BUCKET
