# Least-privilege IAM policies (for a normal AWS account)

AWS Academy Learner Lab **does not allow creating IAM roles**, so the deployed stack
uses the pre-created `LabRole`. These two documents show the least-privilege
permissions each Lambda actually needs; in a real account you would create one
role per function with these policies (replace the UPPER_CASE placeholders) and
set `Role:` on each function in `infra/template.yaml`.

| Function  | Can do                                                                 | Cannot do |
|-----------|------------------------------------------------------------------------|-----------|
| Processor | read `uploads/*` in raw bucket, write `redacted/*` in clean bucket, update DynamoDB, call Comprehend | list buckets, delete, read other tables |
| API       | pre-sign uploads/downloads, CRUD on its own table rows                 | read file contents, call Comprehend |
