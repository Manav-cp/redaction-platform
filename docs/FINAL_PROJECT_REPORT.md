# RedactIQ – Serverless Document Processing and Sensitive Data Redaction Platform

**Degree:** Master of Technology (M.Tech) in Cloud Computing  
**Author:** Manav Maisuriya (Roll No: 26MCE009)  
**AWS Account ID:** 058264205875 | **Region:** us-east-1  
**Live Web Portal:** http://redactiq-frontend-058264205875.s3-website-us-east-1.amazonaws.com  
**GitHub Repository:** https://github.com/Manav-cp/redactiq  

---

## 1. Executive Summary
RedactIQ is a cloud-native serverless platform that removes personal sensitive data (PII) like phone numbers, emails, and SSNs from documents. It uses Amazon S3, AWS Lambda (Python 3.12), Amazon API Gateway, Amazon Cognito, and Amazon DynamoDB. The platform is deployed in AWS Academy Learner Lab and uses a safe GitHub CI/CD pipeline.

## 2. Live Cloud Evidence & AWS Services in Order of Execution

Below are all 19 screenshots from our actual AWS environment, organized in a logical sequence showing how data travels through the system from initial user sign-up to document redaction, monitoring, and deletion.

### Figure 1: Amazon Cognito User Pool - Initial Confirmed Users
**AWS Service:** Amazon Cognito  
![Amazon Cognito User Pool - Initial Confirmed Users](screenshots/Screenshot 2026-11-25 224621.png)  
**Description:** This screen from the Amazon Cognito console shows our user pool (doc-redaction-users). Before running the test, there were three confirmed user accounts. Each user has a unique UUID (the 'sub' claim) which is used throughout the platform to keep user data strictly isolated.

### Figure 2: Amazon Cognito User Pool - New User Account Created
**AWS Service:** Amazon Cognito  
![Amazon Cognito User Pool - New User Account Created](screenshots/Screenshot 2026-11-25 225357.png)  
**Description:** Here we registered a new student account (aksharpatel0201@gmail.com). Cognito verified the email address and marked the account as 'Confirmed' and 'Enabled'. When this user signs in, Cognito provides a signed JWT ID token that gives access to the web portal.

### Figure 3: RedactIQ Web Application - Document Processed and Redacted
**AWS Service:** React SPA & S3 Website  
![RedactIQ Web Application - Document Processed and Redacted](screenshots/Screenshot 2026-11-25 233848.png)  
**Description:** This is our web application running in the browser. The user logged in and uploaded a sample resume (final_resume.pdf). The system processed the file in 344 ms using regex, detected one phone number, masked it, and enabled the 'Download' and 'Delete' buttons.

### Figure 4: RedactIQ Web Portal - Active User Session View
**AWS Service:** React SPA & Cognito Auth  
![RedactIQ Web Portal - Active User Session View](screenshots/Screenshot 2026-11-26 001130.png)  
**Description:** This view shows the top-right header of our portal with the active user email and a 'Sign out' button. The session is managed using the Cognito JWT token stored in memory, so refreshing or closing the browser maintains secure access.

### Figure 5: Amazon API Gateway - Configured HTTP API Routes
**AWS Service:** Amazon API Gateway  
![Amazon API Gateway - Configured HTTP API Routes](screenshots/Screenshot 2026-11-26 000210.png)  
**Description:** This screen shows the Amazon API Gateway console for our API (doc-redaction). It lists the active routes: /upload-url (POST), /documents (GET), and /documents/{docId} (GET, DELETE). Notice that each route has our Cognito JWT authorizer attached so unauthenticated calls are blocked.

### Figure 6: Amazon CloudWatch - API Gateway Access Log Streams
**AWS Service:** Amazon CloudWatch & API Gateway  
![Amazon CloudWatch - API Gateway Access Log Streams](screenshots/Screenshot 2026-11-26 000447.png)  
**Description:** This CloudWatch console view displays the log group (/aws/apigateway/doc-redaction) with 32 log streams. Every request that reaches API Gateway gets logged here with its timestamp, HTTP status, and caller information for security auditing.

### Figure 7: Amazon CloudWatch - Structured API Gateway Access Events
**AWS Service:** Amazon CloudWatch Logs  
![Amazon CloudWatch - Structured API Gateway Access Events](screenshots/Screenshot 2026-11-26 000550.png)  
**Description:** Here are the actual JSON log entries from API Gateway. You can see a POST request to /upload-url returning HTTP status 201 (presigned upload URL generated) and GET requests to /documents returning HTTP status 200 (document ledger loaded).

### Figure 8: Amazon S3 Raw Bucket - Multi-Tenant User Folders
**AWS Service:** Amazon S3 (Raw Ingestion)  
![Amazon S3 Raw Bucket - Multi-Tenant User Folders](screenshots/Screenshot 2026-11-25 234235.png)  
**Description:** This is our S3 raw uploads bucket (doc-redaction-rawbucket-h5gupcq1g7zl). Under the uploads/ folder, files are organized into separate folders named with each user's Cognito UUID. This prevents any user from seeing or modifying files belonging to another person.

### Figure 9: Amazon S3 Raw Bucket - Uploaded Raw PDF File
**AWS Service:** Amazon S3 (Raw Ingestion)  
![Amazon S3 Raw Bucket - Uploaded Raw PDF File](screenshots/Screenshot 2026-11-25 234456.png)  
**Description:** Inside the user's upload folder, you can see the original uploaded document (final_resume.pdf, 161.7 KB). This file contains sensitive information and is stored with AES-256 server-side encryption. A lifecycle rule automatically deletes raw files after 1 day to minimize data risk.

### Figure 10: Amazon CloudWatch - Processor Lambda Log Streams
**AWS Service:** AWS Lambda & CloudWatch  
![Amazon CloudWatch - Processor Lambda Log Streams](screenshots/Screenshot 2026-11-25 235423.png)  
**Description:** This shows the log group for our backend processor Lambda function (doc-redaction-ProcessorFunction-PVh5vCUQlNh7). Seven execution log streams are shown. The function triggers automatically whenever an S3 upload completes.

### Figure 11: AWS Lambda Execution Log - Empirical Duration and Memory
**AWS Service:** AWS Lambda Compute  
![AWS Lambda Execution Log - Empirical Duration and Memory](screenshots/Screenshot 2026-11-25 235627.png)  
**Description:** This is the real execution log of our redaction engine. The Lambda function completed in 353.04 ms, used only 107 MB of memory out of 1024 MB allocated, and outputted a JSON summary: {'event': 'processed', 'piiTotal': 1, 'engine': 'regex', 'ms': 344}.

### Figure 12: Amazon S3 Clean Bucket - Sanitized Output Document
**AWS Service:** Amazon S3 (Clean Storage)  
![Amazon S3 Clean Bucket - Sanitized Output Document](screenshots/Screenshot 2026-11-25 235118.png)  
**Description:** This shows our S3 clean bucket (doc-redaction-cleanbucket-znrkthh4ront). Under redacted/, the processor saved the cleaned document (redacted_final_resume.pdf, 3.7 KB). All sensitive phone numbers and emails have been replaced with redaction labels.

### Figure 13: Amazon DynamoDB - Document Metadata Records and Processing Times
**AWS Service:** Amazon DynamoDB  
![Amazon DynamoDB - Document Metadata Records and Processing Times](screenshots/Screenshot 2026-11-26 000014.png)  
**Description:** This screen from the DynamoDB console shows our table (doc-redaction-DocumentsTable-14FJKZMPAUY2Y). Each row represents a document, storing userId, docId, fileName, status, and actual processing time in milliseconds (206 ms, 228 ms, 233 ms, 240 ms, and 344 ms).

### Figure 14: Amazon CloudWatch Operational Dashboard
**AWS Service:** Amazon CloudWatch Dashboard  
![Amazon CloudWatch Operational Dashboard](screenshots/Screenshot 2026-11-26 000755.png)  
**Description:** This is our live operational dashboard (doc-redaction-dashboard). It shows four real-time graphs: Lambda processor invocations/errors/throttles, processor duration (~353 ms), API request counts (zero 5xx errors), and API latency compared against our 350 ms SLO line.

### Figure 15: Amazon CloudWatch Alarms - All Five Alarms in OK State
**AWS Service:** Amazon CloudWatch Alarms  
![Amazon CloudWatch Alarms - All Five Alarms in OK State](screenshots/Screenshot 2026-11-26 000917.png)  
**Description:** Here are our five CloudWatch alarms: ApiLatencyAlarm, ProcessorErrorsAlarm, Api5xxAlarm, ProcessorDurationAlarm, and ProcessorThrottlesAlarm. All five are in the green 'OK' state, confirming the system is healthy and meeting our SLA targets.

### Figure 16: RedactIQ Web Application - Clean State After Document Deletion
**AWS Service:** React SPA & S3 Website  
![RedactIQ Web Application - Clean State After Document Deletion](screenshots/Screenshot 2026-11-26 001211.png)  
**Description:** After clicking the 'Delete' button on the portal, the document ledger refreshed to show 'No documents yet. Try one of the samples in the samples/ folder.' The live website URL (http://redactiq-frontend-058264205875.s3-website-us-east-1.amazonaws.com) is clearly visible in the browser address bar.

### Figure 17: Amazon S3 Raw Bucket - Proof of Data Cleanup After Deletion
**AWS Service:** Amazon S3 (Data Minimization)  
![Amazon S3 Raw Bucket - Proof of Data Cleanup After Deletion](screenshots/Screenshot 2026-11-26 001344.png)  
**Description:** Returning to the S3 raw bucket, the user's upload folder has been completely deleted. This confirms our data minimization policy: when a user deletes a document, the original raw file with sensitive data is immediately removed from S3.

### Figure 18: Amazon S3 Clean Bucket - Redacted File Deleted from Storage
**AWS Service:** Amazon S3 (Clean Storage)  
![Amazon S3 Clean Bucket - Redacted File Deleted from Storage](screenshots/Screenshot 2026-11-26 001442.png)  
**Description:** Similarly, checking the S3 clean bucket confirms that the redacted output file was also deleted when the user triggered document deletion. No leftover files remain on the storage tier.

### Figure 19: Amazon DynamoDB - Table Record Removed Following Deletion
**AWS Service:** Amazon DynamoDB  
![Amazon DynamoDB - Table Record Removed Following Deletion](screenshots/Screenshot 2026-11-26 001618.png)  
**Description:** Looking at the DynamoDB Items Explorer, the record count dropped from 5 to 4. The deleted document's row was completely removed from the database, confirming full synchronization between the API, S3 storage, and DynamoDB metadata.

## 3. Measured System Performance & Test Results

| Service / Component | Operation | Target SLO | Actual Measured | Status |
|---|---|---|---|---|
| Amazon Cognito | User Authentication | < 5000 ms | 3099.2 ms | PASSED |
| Amazon API Gateway | Presigned URL Request | < 2000 ms | 1017.4 ms | PASSED |
| Amazon S3 (Raw) | Direct File Upload | < 3000 ms | 1945.8 ms | PASSED |
| AWS Lambda (Processor) | TXT Redaction | < 5000 ms | 344 ms (exec 353 ms) | PASSED |
| AWS Lambda (Processor) | PDF Redaction | < 6000 ms | 2600 ms | PASSED |
| Amazon DynamoDB | Metadata Query | < 500 ms | Sub-10 ms | PASSED |
| Amazon CloudWatch | 5 Alarms (Latency, Errors, 5xx) | 5/5 OK | 5/5 OK (0 errors) | PASSED |
| S3 Static Website | Web Portal Delivery | HTTP 200 | HTTP 200 OK | PASSED |
| Multi-Tenancy Guard | Cross-User Document Access | HTTP 404 | HTTP 404 (No Leakage) | PASSED |
| Data Minimization | Document Deletion | Purge S3 & DDB | 100% Cleaned Up | PASSED |

## 4. Conclusion
The 19 screenshots provide concrete proof that RedactIQ is fully functional on AWS. Every component operates within Learner Lab constraints, protects user privacy with zero data leakage, and delivers sub-3-second document redaction.
