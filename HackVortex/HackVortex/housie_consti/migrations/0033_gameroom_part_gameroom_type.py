# Generated by Django 5.1.2 on 2024-12-08 16:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('housie_consti', '0032_alter_case_part_alter_case_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='gameroom',
            name='part',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='gameroom',
            name='type',
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
    ]
