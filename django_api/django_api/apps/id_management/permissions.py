from django.db.models import Q
from rest_framework.permissions import BasePermission

from core.common import PRP_ROLE_TYPES as ROLES


class RoleGroupCreateUpdateDestroyPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        role_in_payload = request.data.get('role') if request.method == 'PATCH' else None
        obj_roles_set = {obj.role, role_in_payload or obj.role}

        if (user == obj.user or
                request.method in ('PATCH', 'DELETE') and (
                obj.role in {ROLES.cluster_system_admin, ROLES.ip_authorized_officer} or
                role_in_payload == obj.role)):
            return False

        # for CLUSTER roles:
        cluster_roles_set = {ROLES.cluster_member, ROLES.cluster_viewer}
        if (obj_roles_set.issubset(cluster_roles_set) and
                user.prp_roles.filter(
                    Q(role=ROLES.cluster_system_admin) |
                    Q(role=ROLES.cluster_imo, cluster__isnull=False, cluster_id=obj.cluster_id) |
                    Q(role=ROLES.cluster_member, user__partner_id__isnull=False, user__partner_id=obj.user.partner_id)
                ).exists()):
            return True

        cluster_roles_set.add(ROLES.cluster_coordinator)
        if (obj_roles_set.issubset(cluster_roles_set) and
                user.prp_roles.filter(
                    Q(role=ROLES.cluster_system_admin) |
                    Q(role=ROLES.cluster_imo, cluster__isnull=False, cluster_id=obj.cluster_id)
                ).exists()):
            return True

        cluster_roles_set.update({ROLES.cluster_imo, ROLES.cluster_system_admin})
        if (obj_roles_set.issubset(cluster_roles_set) and
                user.prp_roles.filter(
                    role=ROLES.cluster_system_admin
                ).exists()):
            return True

        if obj_roles_set.intersection(cluster_roles_set):
            return False

        # for IP roles:
        if user.partner_id == obj.user.partner_id:
            if ((ROLES.ip_admin == role_in_payload or
                 obj.role == ROLES.ip_admin and request.method in ('POST', 'DELETE')) and
                    user.prp_roles.filter(
                        role=ROLES.ip_authorized_officer, workspace__isnull=False, workspace_id=obj.workspace_id
                    ).exists()):
                return True

            if (obj_roles_set.issubset({ROLES.ip_editor, ROLES.ip_viewer}) and
                    user.prp_roles.filter(
                        role=ROLES.ip_admin, workspace__isnull=False, workspace_id=obj.workspace_id
                    ).exists()):
                return True

        return False