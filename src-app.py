import boto3
import json
import logging
import time
import os
import requests
import traceback
import urllib
from jose import jwk, jwt
from jose.utils import base64url_decode
from http import cookies
from botocore.exceptions import ClientError

region = os.environ['AWS_REGION'] # 'eu-west-1'
userpool_id = os.environ['USERPOOL_ID'] # 'eu-west-1_XYZ'
app_client_id = os.environ['CLIENT_ID'] # 'qqfqqfqqfqqfqqfqqfqqf'
app_client_secrect = os.environ['CLIENT_SECRET']
login_domain = os.environ['LOGIN_DOMAIN']
s3_bucket = os.environ['S3_BUCKET']

login_url = 'https://{}.auth.{}.amazoncognito.com'.format(login_domain, region)
keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(region, userpool_id)

# instead of re-downloading the public keys every time
# we download them only on cold start
# https://aws.amazon.com/blogs/compute/container-reuse-in-lambda/
with urllib.request.urlopen(keys_url) as f:
  response = f.read()
keys = json.loads(response.decode('utf-8'))['keys']


def parse_token(identity):
    token = identity['id_token']
    # get the kid from the headers prior to verification
    headers = jwt.get_unverified_headers(token)
    kid = headers['kid']
    # search for the kid in the downloaded public keys
    key_index = -1
    for i in range(len(keys)):
        if kid == keys[i]['kid']:
            key_index = i
            break
    if key_index == -1:
        print('Public key not found in jwks.json')
        return False
    # construct the public key
    public_key = jwk.construct(keys[key_index])
    # get the last two sections of the token,
    # message and signature (encoded in base64)
    message, encoded_signature = str(token).rsplit('.', 1)
    # decode the signature
    decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
    # verify the signature
    if not public_key.verify(message.encode("utf8"), decoded_signature):
        print('Signature verification failed')
        return False
    print('Signature successfully verified')
    # since we passed the verification, we can now safely
    # use the unverified claims
    claims = jwt.get_unverified_claims(token)
    # additionally we can verify the token expiration
    if time.time() > claims['exp']:
        print('Token is expired')
        return False
    # and the Audience  (use claims['client_id'] if verifying an access token)
    if claims['aud'] != app_client_id:
        print('Token was not issued for this audience')
        return False
    # now we can use the claims
    print(claims)
    return claims
    

def get_user_identity(code, callback_uri):
    token_url = f"{login_url}/oauth2/token"
    auth = requests.auth.HTTPBasicAuth(app_client_id, app_client_secrect)
    
    params = {
        "grant_type": "authorization_code",
        "client_id": app_client_id,
        "code": code,
        "redirect_uri": callback_uri
    }
    print("get_user_identity::params: ", params)
    
    response = requests.post(token_url, auth=auth, data=params).json()
    if 'error' in response:
        raise Exception("Error in response: ", response)
        
    print("get_user_identity result:", response)
    return response


def build_download_list(bucket_name, Order_Number, expiration=3600):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    
    links = []
    for o in bucket.objects.filter(Prefix="Software/"):
        links.append('<li><a href="{}">{}</a></li>'.format(create_presigned_url(s3_bucket, o.key, expiration), o.key))
        
    for o in bucket.objects.filter(Prefix=f"{Order_Number}/"):
        links.append('<li><a href="{}">{}</a></li>'.format(create_presigned_url(s3_bucket, o.key, expiration), o.key))        
        
    return "\n".join(links)


def create_presigned_url(bucket_name, object_name, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={ 'Bucket': bucket_name,
                                                             'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response


def redirect(login_redirect):
    print("redirect to URL: ", login_redirect)
    body = f"""<a href="{login_redirect}" > weiter mit der Authenfizierung</a>"""
    return { "statusCode": 200, "headers": { 'Content-Type': 'text/html' }, "body": body }


def lambda_handler(event, context):
    print(os.environ)
    print(json.dumps(event))

    redirect_url = "https://{}{}".format(event['headers']['Host'], event['requestContext']['path']) 
    login_redirect = "{}/oauth2/authorize?client_id={}&response_type=code&scope=email+openid+profile&redirect_uri={}".format(login_url, app_client_id, urllib.parse.quote_plus(redirect_url))

    try:
        code = event['queryStringParameters'] and event['queryStringParameters'].get('code')
        if code:
            
            cookie_header = event['headers'] and event['headers'].get('cookie')
            if cookie_header:
                c = cookies.SimpleCookie()
                c.load(cookie_header)
                print("Read refresh_token from header", c['refresh_token'].value)
            
            print("lambda_handler: ", code)
            identity = get_user_identity(code, redirect_url)
            print("identity:", identity)
            claims = parse_token(identity)
            
            #presinged_link = create_presigned_url(s3_bucket, "{}/licence.key".format(claims['custom:Order_Number']), 120)
            #print("presinged_link: ", presinged_link)
    
            body = """<h1>{}</h1>
                      <p>Hello {} ({})</p>
                      <h2> Your downloads </h2>
                      <ul>{}</ul>
                   """.format(code, claims['email'], claims['custom:C_Number'], build_download_list(s3_bucket, claims['custom:Order_Number'], 120)) 
                   #create_presigned_url(s3_bucket, "Software/my.iso", 120). 
    
            #c = cookies.SimpleCookie()
            #c['refresh_token'] = identity['refresh_token']
            #print(c.output())

            return { "statusCode": 200, "headers": { 'Content-Type': 'text/html', 'Set-Cookie' : "refresh_token={}".format(identity['refresh_token']) }, "body": body }

        else:
            # https://my-downloads.auth.eu-west-1.amazoncognito.com/oauth2/authorize?client_id=60e0sig4&response_type=code&scope=email+openid+profile&redirect_-1.amazonaws.com%2FProd%2Fdownload
            # https://my-downloads.auth.eu-west-1.amazoncognito.com/login?client_id=3hd9&response_type=code&scope=email+openid+profile&redirect_uri=https://Fh9kormc0i4.execute-api.eu-westnaws.com/Prod/download
            #login_redirect = "{}/oauth2/authorize?client_id={}&response_type=code&scope=email+openid+profile&redirect_uri={}".format(login_url, app_client_id, urllib.parse.quote_plus(redirect_url))
            print("redirect to URL: ", login_redirect)
            return { "statusCode": 302, "headers": { 'Location': login_redirect } }
        
    except Exception as ex:
        print("lambda_handler::Exception:" + str(ex))
        traceback.print_tb(ex.__traceback__)
        
        return redirect(login_redirect)

        # return { "statusCode": 501 }
        # raise Exception("Error in code")


# the following is useful to make this script executable in both
# AWS Lambda and any other local environments
if __name__ == '__main__':
    # for testing locally you can enter the JWT ID Token here
    event = {'token': 'eyJraWQiOiJnQ1wvRWhNY2luMVJ1ZTJYSWt4Vlg1bmlLcVVVVHl1TjljQ2JETUd3Sm5EMD0iLCJhbeyJraWQiOiJnQ1wvRWhNY2luMVJ1ZTJYSWt4Vlg1bmlLcVVVVHl1TjljQ2JETUd3Sm5EMD0iLCJhbeyJraWQiOiJnQ1wvRWhNY2luMVJ1ZTJYSWt4Vlg1bmlLcVVVVHl1TjljQ2JETUd3Sm5EMD0iLCJhbeyJraWQiOiJnQ1wvRWhNY2luMVJ1ZTJYSWt4Vlg1bmlLcVVVVHl1TjljQ2JETUd3Sm5EMD0iLCJhb'}
    lambda_handler(event, None)
