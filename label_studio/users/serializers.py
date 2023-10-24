"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.
"""
from core.feature_flags import flag_set
from core.utils.common import load_func
from django.conf import settings
from organizations.models import OrganizationMember
from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import serializers

from .models import User


class BaseUserSerializer(FlexFieldsModelSerializer):
    # short form for user presentation
    initials = serializers.SerializerMethodField(default='?', read_only=True)
    avatar = serializers.SerializerMethodField(read_only=True)

    def get_avatar(self, user):
        return user.avatar_url

    def get_initials(self, user):
        if flag_set('fflag_feat_all_optic_114_soft_delete_for_churned_employees', user=user):
            return user.get_initials(self._is_deleted(user))
        else:
            return user.get_initials()

    def _is_deleted(self, instance):
        if organization_members := self.context.get('organization_members', None):
            organization_member_for_user = next(
                (
                    organization_member
                    for organization_member in organization_members
                    if organization_member.user_id == instance.id
                ),
                None,
            )
        else:
            org_id = (
                self.context['user'].active_organization_id
                if 'user' in self.context
                else self.context['request'].user.active_organization_id
            )
            organization_member_for_user = OrganizationMember.objects.get(user_id=instance.id, organization_id=org_id)
        return bool(organization_member_for_user.deleted_at)

    def to_representation(self, instance):
        """Returns user with cache, this helps to avoid multiple s3/gcs links resolving for avatars"""

        uid = instance.id
        key = 'user_cache'

        if key not in self.context:
            self.context[key] = {}
        if uid not in self.context[key]:
            self.context[key][uid] = super().to_representation(instance)

        if flag_set('fflag_feat_all_optic_114_soft_delete_for_churned_employees', user=instance):
            if self._is_deleted(instance):
                for field in ['username', 'first_name', 'last_name', 'email']:
                    self.context[key][uid][field] = 'USER' if field == 'last_name' else 'DELETED'
        return self.context[key][uid]

    class Meta:
        model = User
        fields = (
            'id',
            'first_name',
            'last_name',
            'username',
            'email',
            'last_activity',
            'avatar',
            'initials',
            'phone',
            'active_organization',
            'allow_newsletters',
        )


class BaseUserSerializerUpdate(BaseUserSerializer):
    class Meta(BaseUserSerializer.Meta):
        read_only_fields = ('email',)


class UserSimpleSerializer(BaseUserSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'avatar')


UserSerializer = load_func(settings.USER_SERIALIZER)
UserSerializerUpdate = load_func(settings.USER_SERIALIZER_UPDATE)
