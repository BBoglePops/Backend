# Generated by Django 5.0.4 on 2024-06-15 07:35

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('InterviewAnalyze', '0001_initial'),
        ('QuestionList', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewanalysis',
            name='question_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='QuestionList.questionlists'),
        ),
    ]
