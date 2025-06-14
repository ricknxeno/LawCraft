# Generated by Django 5.1.2 on 2024-12-03 15:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spinwheel', 'new_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='CardCombo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('bonus_coins', models.IntegerField(default=0)),
                ('required_cards', models.ManyToManyField(to='spinwheel.card')),
            ],
        ),
        migrations.CreateModel(
            name='PlayerComboProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_completed', models.BooleanField(default=False)),
                ('combo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spinwheel.cardcombo')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spinwheel.playerprofile')),
            ],
            options={
                'unique_together': {('player', 'combo')},
            },
        ),
    ]
