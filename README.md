# Smart Image Analysis Application

**Platform:** AWS Academy Learner Lab (us-east-1)
**Author:** Ramsha
**Date:** July 5, 2026

---

## 1. Problem Statement

A company wants to automatically understand the content of images it receives — identifying objects, scenes, facial expressions, and whether people in the photo are smiling — without manual review. This application analyzes uploaded images and stores the analysis results for later retrieval.

---

## 2. Solution Architecture

```
Image Upload → Amazon S3 → AWS Lambda (trigger) → Amazon Rekognition → Amazon DynamoDB
```

**AWS Services used:**
- Amazon S3 — image storage and event trigger source
- AWS Lambda — event-driven compute, orchestrates the analysis
- Amazon Rekognition — DetectLabels (objects/scenes) + DetectFaces (emotion/smile)
- Amazon DynamoDB — persists combined analysis results

**Environment note:** Built entirely on AWS Academy Learner Lab, which restricts custom IAM role creation. All services (Lambda, S3, Rekognition, DynamoDB) were configured to use the pre-provisioned **`LabRole`** execution role instead of a custom IAM policy.

---

## 3. Implementation Steps

### 3.1 S3 Bucket Setup
- Created bucket: `ramsha-smart-img-analysis` (us-east-1)
- Created folder: `images-input/`
- Configured an event notification for `s3:ObjectCreated:*` events with prefix `images-input/`, targeting the Lambda function

### 3.2 DynamoDB Table
- Table name: `ImageAnalysisResults`
- Partition key: `image_id` (String) — uses the S3 object key as the unique identifier
- Capacity mode: On-demand (default settings)

### 3.3 Lambda Function
- Function name: `ImageAnalysisFunction`
- Runtime: Python 3.12
- Execution role: `LabRole` (existing role, selected via "Custom execution role" toggle)
- Timeout: increased from default 3s → **30s** (Rekognition calls need more time)
- Memory: increased from default 128MB → **256MB**
- Trigger: S3 `ramsha-smart-img-analysis` bucket, prefix `images-input/`, all object create events

**Core Lambda logic:**

```python
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
```

### 3.4 Verification
- Confirmed successful execution via CloudWatch Logs (no errors, `START`→`END`→`REPORT` sequence, ~731ms duration)
- Queried DynamoDB via "Explore items" / Scan to confirm records were written correctly

---

## 4. Test Results

Five images were uploaded to validate the pipeline across different scenarios:

| # | Image | Faces Detected | Notable Result |
|---|---|---|---|
| 1 | images.jpg | 1 | HAPPY, 100% confidence; smile=true (99.96%) |
| 2 | 215441473_e1.jpeg | 0 (no people) | Labels correctly identified: Teddy Bear, Toy, Plush, Remote Control — `faces: []` returned cleanly |
| 3 | emotions.jpeg | 9 | Varied emotions correctly distinguished: Happy, Surprised, Sad, Angry, Calm, Confused |
| 4 | common-emotions.jpg | 24 | Large multi-face collage handled without timeout or error; mixed emotions detected accurately |
| 5 | 360_F_215952710...jpg | 1 | SAD, 99.3% confidence; smile=false (correctly not flagged as happy) |

**Key observations:**
- The pipeline correctly returns an empty `faces` list when no people are present, rather than erroring.
- Emotion classification remained accurate even with a large number of simultaneous faces (24 in one image).
- Smile detection correctly differentiated true/false with high confidence scores — did not default to "true."

### Sample stored record (DynamoDB item)

```json
{
  "image_id": "images-input/images.jpg",
  "faces": [
    {
      "emotion": "HAPPY",
      "emotion_confidence": "100.0",
      "smile": true,
      "smile_confidence": "99.9570541381836"
    }
  ],
  "labels": [
    {"confidence": "99.99464416503906", "name": "Head"},
    {"confidence": "99.99464416503906", "name": "Person"},
    {"confidence": "99.99150085449219", "name": "Face"},
    {"confidence": "99.96414184570312", "name": "Happy"},
    {"confidence": "99.96414184570312", "name": "Smile"},
    {"confidence": "99.9078369140625", "name": "Body Part"},
    {"confidence": "99.9078369140625", "name": "Neck"},
    {"confidence": "98.71244812011719", "name": "Photography"},
    {"confidence": "94.8072280883789", "name": "Portrait"}
  ],
  "timestamp": "2026-07-05T15:26:50.338510"
}
```

---

## 5. Expected Output / Deliverables Mapping

| Expected Output | Description | Status |
|---|---|---|
| Detected objects/labels | List of objects/scenes with confidence scores | ✅ Delivered |
| Facial analysis | Emotion classification with confidence scores | ✅ Delivered |
| Smile detection | True/false smile result with confidence score | ✅ Delivered |
| DynamoDB records | One record per analyzed image, combining all results | ✅ Delivered |

---

## 6. Challenges & Resolutions

- **IAM restrictions in Learner Lab:** Custom IAM roles could not be created. Resolved by using the pre-provisioned `LabRole` for Lambda's execution role, which already has permissions for S3, Rekognition, and DynamoDB access.
- **Default Lambda timeout too short:** The default 3-second timeout caused early failures. Resolved by increasing timeout to 30 seconds and memory to 256MB.
- **Region lock:** Learner Lab restricts service access to us-east-1 (and us-west-2). All resources were created in us-east-1 to avoid cross-region access errors.

---

## 7. Conclusion

The Smart Image Analysis Application successfully demonstrates an event-driven, serverless architecture on AWS. Uploading an image to S3 automatically triggers analysis via Rekognition (both label and face detection), with combined results persisted to DynamoDB for later retrieval — fulfilling all requirements of the project brief with no manual intervention required at any step.
