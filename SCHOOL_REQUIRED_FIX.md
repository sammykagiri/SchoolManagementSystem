# Fix for "school_id violates not-null constraint" Error

## The Problem

You're seeing errors like:
```
null value in column "school_id" of relation "core_grade" violates not-null constraint
```

This happens because:
1. **No School record exists** in your database, OR
2. **Your user profile is not associated with a School**

The `Grade` model requires a `school` foreign key - every grade must belong to a school.

## The Solution

### Step 1: Create a School Record

You need to create a School first. Here's how:

#### Option A: Create School via Django Admin

1. Log into the admin panel: `https://your-railway-app.railway.app/admin/`
2. Go to **Core** → **Schools**
3. Click **"Add School"**
4. Fill in the required fields:
   - Name: Your school name (e.g., "ABC Primary School")
   - Address: School address
   - Email: School email
   - Phone: School phone number
   - (Optional) Logo: Upload school logo
5. Click **"Save"**

#### Option B: Create School via Application

If your application has a school creation page, use that.

### Step 2: Associate School with Your User Profile

After creating the school:

1. Go to **Core** → **User Profiles** in the admin panel
2. Find your user profile
3. Edit it and set the **School** field to the school you just created
4. Save

### Step 3: Now You Can Create Grades

Once your user profile has a school associated:
- The grade creation forms will automatically use your school
- Grades will be created with the correct `school_id`
- No more null constraint errors!

## Why This Happens

The application is **multi-tenant** - it supports multiple schools. Therefore:
- Every grade must belong to a school
- Every student must belong to a school
- Every class must belong to a school
- etc.

When you try to create a grade without a school, Django tries to insert `NULL` for `school_id`, which violates the database constraint.

## Quick Fix via Railway CLI (If Needed)

If you need to create a school quickly via command line:

```bash
# Using Railway CLI
railway run python manage.py shell
```

Then in the shell:
```python
from core.models import School, UserProfile

# Create a school
school = School.objects.create(
    name="Your School Name",
    address="Your School Address",
    email="school@example.com",
    phone="+1234567890"
)

# Associate with your user (replace 'admin' with your username)
from django.contrib.auth.models import User
user = User.objects.get(username='admin')
profile, created = UserProfile.objects.get_or_create(user=user)
profile.school = school
profile.save()

print(f"Created school: {school.name}")
print(f"Associated with user: {user.username}")
```

## Prevention

To prevent this in the future:
1. **Always create a School first** before creating other records
2. **Ensure user profiles have schools** associated
3. **Use the application's setup wizard** (if available) to initialize your school

## Verification

After creating a school and associating it:

1. Check your user profile has a school:
   ```python
   # In Django shell or via admin
   user.profile.school  # Should not be None
   ```

2. Try creating a grade again - it should work now!

3. All subsequent operations (students, classes, etc.) will use this school



