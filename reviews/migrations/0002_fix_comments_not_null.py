from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='comments',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='review',
            name='recommendation',
            field=models.CharField(blank=True, max_length=20, null=True, choices=[
                ('accept', 'Kabul'),
                ('minor_revision', 'Küçük Revizyon'),
                ('major_revision', 'Büyük Revizyon'),
                ('reject', 'Red'),
            ]),
        ),
    ] 