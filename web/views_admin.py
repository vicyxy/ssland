#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django import forms
from django.shortcuts import render, redirect
from django.contrib.auth import forms as auth_forms
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, permission_required
from web.models import ProxyAccount, Quota

from web.views import FlickBackResponse
from core.util import random_password
from collections import OrderedDict
import json

@permission_required('auth.add_user')
def user_list(request):
    user_account = {}
    user_user = {}
    mix_out = []

    for pa in ProxyAccount.objects.all():
        pk = pa.user.pk
        if not pk in user_account: 
            user_account[pk] = []
            user_user[pk] = pa.user
        user_account[pk].append(pa)
    
    pks_sorted = user_user.keys()
    pks_sorted.sort()
    for pk in pks_sorted:
        mix_out.append((user_user[pk], user_account[pk]))
    
    return render(request, 'admin/users.html', {
        'title': 'Users', 
        'mix': mix_out,
    })

class UserAddForm(auth_forms.UserCreationForm):
    pass

@permission_required('auth.add_user')
def user_add(request):
    if request.method == "POST":
        form = UserAddForm(request.POST)
        if form.is_valid():
            u = form.save()
            import config as ssland_config
            from service import getService
            for service_name in ssland_config.MODULES:
                s = getService(service_name)
                conf = s.skeleton()
                a = ProxyAccount(user=u, service=service_name, enabled=False, config=conf)
                a.save()
            return redirect('..')
    else:
        form = UserAddForm()
    return render(request, 'admin/user.add.html', {
        'title': 'Add User',
        'form': form,
    })

@permission_required('auth.add_user')
def user_toggle(request, uid):
    if str(uid) == str(request.user.pk):
        return FlickBackResponse(request)

    u = User.objects.get(pk=uid)
    u.is_active = not u.is_active
    u.save()

    for pa in ProxyAccount.objects.filter(user=u, enabled=True):
        try:
            if u.is_active: pa.start_service()
            else: pa.stop_service()
        except:
            pass
        
    return FlickBackResponse(request)

@permission_required('web.change_proxyaccount')
def account_toggle(request, account_id):
    account = ProxyAccount.objects.get(pk=account_id)
    account.enabled = not account.enabled
    account.save()
    return FlickBackResponse(request)

@permission_required('web.change_proxyaccount')
def account_edit(request, account_id):
    account = ProxyAccount.objects.get(pk=account_id)
    UserForm = account.adminForm
    prevURL =   request.POST['prev'] if 'prev' in request.POST else                 \
                request.META['HTTP_REFERER'] if 'HTTP_REFERER' in request.META else \
                '/'

    if request.method == "POST":
        form = UserForm(request.POST)
        bypass_twostep_validate = not getattr(form, 'is_valid_for_account', None)
        if form.is_valid() and (bypass_twostep_validate or form.is_valid_for_account(account)):
            account.config.update(form.cleaned_data)
            account.save()
            return redirect(prevURL)
    else:
        form = UserForm(initial=account.config)
    
    quotas = []
    for quota in Quota.objects.filter(account=account):
        quota.update_from_alias()
        quotas.append({
            'id': quota.pk,
            'name': quota.name,
            'desc': quota.descript(True),
            'enabled': quota.enabled,
            'o': quota,
        })

    return render(request, 'account.edit.html', {
        'title': 'Edit Account', 
        'account': account,
        'prev': prevURL,
        'form': form,
        'quotas': quotas,
    })

@permission_required('web.change_proxyaccount')
def quota_add(request, account_id):
    q = Quota(account_id=account_id)
    q.save()
    return FlickBackResponse(request)

@permission_required('web.change_proxyaccount')
def quota_toggle(request, quota_id):
    quota = Quota.objects.get(pk=quota_id)
    quota.enabled = not quota.enabled 
    quota.save()
    return FlickBackResponse(request)

@permission_required('web.change_proxyaccount')
def quota_reset(request, quota_id):
    quota = Quota.objects.get(pk=quota_id)
    quota.reset()
    quota.save()
    return FlickBackResponse(request)

@permission_required('web.change_proxyaccount')
def quota_remove(request, quota_id):
    quota = Quota.objects.get(pk=quota_id)
    quota.delete()
    return FlickBackResponse(request)

@permission_required('web.change_proxyaccount')
def quota_edit(request, quota_id):
    from quota import getQuotaTypes
    quota = Quota.objects.get(pk=quota_id)
    ModuleFormCls = quota.module.Form
    prevURL =   request.POST['prev'] if 'prev' in request.POST else                 \
                request.META['HTTP_REFERER'] if 'HTTP_REFERER' in request.META else \
                '/'

    class FormCls(ModuleFormCls):
        _quota_type = forms.ChoiceField(choices=getQuotaTypes(), initial=quota.type, label='Quota Type', help_text='Change will be applied after clicking "Save"')
        _enabled = forms.BooleanField(initial=quota.enabled, label='Enabled', required=False)
        _last_trigged = forms.DateTimeField(initial=quota.last_trigged, label='Last Trigged')
    
    if request.method == "POST":
        form = FormCls(request.POST)
        if form.is_valid():
            fdata = form.cleaned_data
            if fdata['_quota_type'] != quota.type:
                quota.type = fdata['_quota_type']
                quota.save()
                return redirect(request.path)
            quota.enabled = fdata['_enabled']
            quota.last_trigged = fdata['_last_trigged']
            del fdata['_quota_type']
            del fdata['_enabled']
            del fdata['_last_trigged']
            quota.param.update(fdata)
            quota.save()
            return redirect(prevURL)
    else:
        form = FormCls(initial=quota.param)

    return render(request, 'admin/quota.edit.html', {
        'title': 'Edit Quota',
        'prev': prevURL,
        'form': form,
        'quota': quota,
    })
