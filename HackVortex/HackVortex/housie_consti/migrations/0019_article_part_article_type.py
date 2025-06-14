# Generated by Django 5.1.3 on 2024-12-06 12:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('housie_consti', '0018_gameroom_current_case_index_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='part',
            field=models.IntegerField(choices=[(5, 'Part 5'), (6, 'Part 6')], default=5),
        ),
        migrations.AddField(
            model_name='article',
            name='type',
            field=models.CharField(choices=[('JUD', 'Judiciary'), ('LEG', 'Legislative'), ('EXEC', 'Executive')], default='LEG', max_length=4),
        ),
    ]
