# Generated by Django 5.1.3 on 2024-12-06 18:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snake_ladder', '0016_alter_cellcontent_part_alter_cellcontent_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cell',
            name='content',
        ),
        migrations.RemoveField(
            model_name='cell',
            name='topic',
        ),
        migrations.AddField(
            model_name='cell',
            name='contents',
            field=models.ManyToManyField(blank=True, related_name='cells', to='snake_ladder.cellcontent'),
        ),
    ]
