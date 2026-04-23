# IU Marketplace System - Deploy-Ready Flask Version

This package contains a deployment-ready backend version of your IU Marketplace System.

## Included deployment changes
- Environment-based database configuration using `DATABASE_URL`
- Environment-based `SECRET_KEY`
- Cleaned duplicate imports
- Stronger login/block/hidden checks
- Explicit listing defaults on creation
- Vercel configuration via `vercel.json`
- `requirements.txt`, `.env.example`, and `.gitignore`

## Important limitation
This version still saves uploaded images to `static/uploads`.
That works locally, but Vercel does not provide reliable persistent filesystem storage for user uploads.
For full production deployment, move image storage to Cloudinary, S3, or Supabase Storage.

## Local run
```bash
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Then visit:
- http://127.0.0.1:5000/init-db
- http://127.0.0.1:5000/

## Vercel deployment
1. Push the project to GitHub
2. Import it into Vercel
3. Add these Environment Variables in Vercel:
   - `SECRET_KEY`
   - `DATABASE_URL`
   - `DEFAULT_ADMIN_EMAIL`
   - `DEFAULT_ADMIN_PASSWORD`
4. Redeploy
5. Open `/init-db` once after deployment

## Recommended database
Use PostgreSQL from Railway, Neon, Supabase, or another cloud provider.
