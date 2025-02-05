from unittest import mock
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import validate_subscribers_group
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_for_user
from zerver.models import NamedUserGroup, UserGroup, UserProfile, Stream

class TestValidateSubscribersGroup(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("iago")
        self.realm = self.user.realm
        self.stream = Stream.objects.get(realm=self.realm)
        # Ensure the system group "@role:nobody" exists
        try:
            self.nobody_group = UserGroup.objects.get(
                named_user_group__name="@role:nobody",
                realm=self.realm
        )
        except UserGroup.DoesNotExist:
            nobody_named_group = NamedUserGroup.objects.create(
                name="@role:nobody",
                realm=self.realm,
                is_system_group=True,
                # Set a temporary reference to itself to satisfy not-null constraint
                can_mention_group=UserGroup.objects.create(realm=self.realm)
            )
        self.nobody_group = nobody_named_group.user_group
        
        # Now update the can_mention_group to point to itself
        nobody_named_group.can_mention_group = self.nobody_group
        nobody_named_group.save()

    def test_system_group_with_valid_role(self) -> None:
        # Get system group using proper API: call with only self.realm
        admin_group = get_system_user_group_for_user(self.realm)
        admin_user = self.example_user("iago")
        
        result_group = validate_subscribers_group(
            admin_group, self.stream, {}, admin_user
        )
        self.assertEqual(result_group, admin_group)

    def test_system_group_with_invalid_role(self) -> None:
        admin_group = get_system_user_group_for_user(self.realm)
        member_user = self.example_user("hamlet")

        with self.assertRaisesRegex(JsonableError, "Insufficient permission"):
            validate_subscribers_group(
                admin_group, self.stream, {}, member_user
            )

    def test_non_system_group_member(self) -> None:
        custom_group = NamedUserGroup.objects.create(
            name="Test Custom Group",
            realm=self.realm,
            is_system_group=False,
            can_mention_group=self.nobody_group
        )
        member_user = self.example_user("hamlet")
        custom_group.direct_members.add(member_user)

        with mock.patch.object(UserProfile, 'is_in_group', return_value=True):
            result_group = validate_subscribers_group(
                custom_group, self.stream, {}, member_user
            )
            self.assertEqual(result_group, custom_group)

    def test_non_system_group_non_member(self) -> None:
        custom_group = NamedUserGroup.objects.create(
            name="Test Custom Group 2",
            realm=self.realm,
            is_system_group=False,
            can_mention_group=self.nobody_group
        )
        non_member_user = self.example_user("cordelia")

        with mock.patch.object(UserProfile, 'is_in_group', return_value=False):
            with self.assertRaisesRegex(JsonableError, "Insufficient permission"):
                validate_subscribers_group(
                    custom_group, self.stream, {}, non_member_user
                )

    def test_invalid_group_id(self) -> None:
        acting_user = self.example_user("iago")
        with self.assertRaisesRegex(JsonableError, "Invalid group configuration"):
            validate_subscribers_group(9999, self.stream, {}, acting_user)