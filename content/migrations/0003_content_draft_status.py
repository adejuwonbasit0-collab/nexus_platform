from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('content', '0002_content_thumbnail_url'),
    ]
    operations = [
        migrations.AlterField(
            model_name='content',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('draft','Draft'),('pending','Pending Review'),('approved','Approved'),('rejected','Rejected')],
                default='pending',
            ),
        ),
    ]
