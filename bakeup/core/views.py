from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin

# Create your views here.

class BasePermissionsMixin(LoginRequiredMixin):
    pass