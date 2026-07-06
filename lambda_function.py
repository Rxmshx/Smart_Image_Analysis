"""
Smart Image Analysis Application — AWS Lambda Function
Triggered by: S3 ObjectCreated events (bucket: ramsha-smart-img-analysis, prefix: images-input/)
Services used: Amazon S3, Amazon Rekognition, Amazon DynamoDB
Execution role: LabRole (AWS Academy Learner Lab)
"""

import boto3
import json
from datetime import datetime

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ImageAnalysisResults')


def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # DetectLabels - objects/scenes
    labels_response = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': bucket, 'Name': key}},
        MaxLabels=10,
        MinConfidence=70
    )

    # DetectFaces - emotions/smile
    faces_response = rekognition.detect_faces(
        Image={'S3Object': {'Bucket': bucket, 'Name': key}},
        Attributes=['ALL']
    )

    faces_data = []
    for face in faces_response['FaceDetails']:
        top_emotion = max(face['Emotions'], key=lambda e: e['Confidence'])
        faces_data.append({
            'emotion': top_emotion['Type'],
            'emotion_confidence': str(top_emotion['Confidence']),
            'smile': face['Smile']['Value'],
            'smile_confidence': str(face['Smile']['Confidence'])
        })

    table.put_item(Item={
        'image_id': key,
        'labels': [{'name': l['Name'], 'confidence': str(l['Confidence'])} for l in labels_response['Labels']],
        'faces': faces_data,
        'timestamp': datetime.utcnow().isoformat()
    })

    return {'statusCode': 200, 'body': json.dumps('Analysis complete')}
