from django.db import models
from django.contrib.auth.models import User
from compsoc.settings import DATE_FORMAT_STRING,QUOTA_INC
from compsoc.shortcuts import *
from datetime import datetime, timedelta
from django.db.models.signals import post_save,post_delete,m2m_changed,pre_save
from memberinfo.mailman import subscribe_member,unsubscribe_member,MailmanError

# All information about a member, that isn't stored by auth...User, and isn't optional
class Member(models.Model):
    """
    Used to store auxiliary data to the default profile data for
    a django User.
    """
    user = models.OneToOneField(User)
    showDetails = models.BooleanField()
    guest = models.BooleanField()

    def is_fresher(self):
        return self.user.username.startswith("%02d" % (date.today().year-2000))

    def is_normal(self):
        return not (self.is_fresher() or self.guest)

    def name(self):
        try:
            nick = self.user.nicknamedetails.nickname
            if nick.strip():
                return nick
        except: pass
        return self.user.get_full_name()

    def all_name(self):
        try:
            return self.user.nicknamedetails.nickname+" ("+self.user.get_full_name()+")"
        except NicknameDetails.DoesNotExist:
            return self.user.get_full_name()
    
    def get_nick(self):
        try:
            return self.user.nicknamedetails.nickname
        except NicknameDetails.DoesNotExist:
            return ""

    def __unicode__(self):
        return self.name()

class GuestReason(models.Model):
    """
    Reflects a reason for a particular account wanting to be a guest account
    """
    user = models.OneToOneField(User)
    reason = models.TextField(help_text="This should reflect why you want a guest account and want your connection to the society is")

# Optional info about one's website
class WebsiteDetails(models.Model):
    user = models.OneToOneField(User)
    websiteUrl = models.CharField(max_length=50)
    websiteTitle = models.CharField(max_length=50)

class NicknameDetails(models.Model):
    user = models.OneToOneField(User)
    nickname = models.CharField(max_length=20)

# Optional info for ones' gaming identities

class GamingIDs(models.Model):
    user = models.OneToOneField(User)
    steamID = models.CharField(max_length=50)
    xboxID = models.CharField(max_length=50)
    psnID = models.CharField(max_length=50)
    xfireID = models.CharField(max_length=50)

class MemberJoin(models.Model):
    '''Stores history of membership'''
    user = models.ForeignKey(User)
    year = models.IntegerField()

    def __unicode__(self):
        return "%s joined in %i" % (self.user.username,self.year)

TERMS = (
    ('AU','Autumn'),
    ('SP','Spring'),
    ('SU','Summer'),
)

class Term(models.Model):
    """
    Stores date information about terms
    """
    start_date = models.DateField()
    start_number = models.IntegerField()
    length = models.IntegerField()
    which = models.CharField(max_length=2,choices=TERMS)

    def __unicode__(self):
        return "%s term %i" % (self.get_which_display(), self.start_date.year)

def term_for(date):
    candidate = Term.objects.filter(start_date__lte=date).latest('start_date')
    within = timedelta(days=(candidate.length)*7)
    if date < (candidate.start_date + within):
        return candidate
    else:
        raise Term.DoesNotExist

def term_week_for(date):
    term = term_for(date)
    return ((date - term.start_date).days / 7) + 1

def warwick_week_for(date):
    if type(date) is datetime:
        date = date.date()
    term = term_for(date)
    return ((date - term.start_date).days / 7) + term.start_number# + 1

STATUS = (
    ('RE','Requested'),
    ('PR','Present'),
    ('DD','Disabled'),
)

    # The user has stated that he/she/undefined wants quota
    # the user has paid, but the account hasn't been changed
    # the change has been made
QUOTA_STATUS = (
    ('RE','Requested'),
    ('AU','Authorised'),
    ('PR','Present'),
)

class ShellAccount(models.Model):
    user = models.OneToOneField(User)
    name = models.CharField(max_length=30)
    status = models.CharField(max_length=2,choices=STATUS)
    
    def isPresent(self):
        return self.status == 'PR'

    def isDisabled(self):
        return self.status == 'DD'
    
    def __unicode__(self):
        return self.name

class DatabaseAccount(models.Model):
    user = models.OneToOneField(User)
    name = models.CharField(max_length=30)
    status = models.CharField(max_length=2,choices=STATUS)
    
    def isPresent(self):
        return self.status == 'PR'
    
    def isDisabled(self):
        return self.status == 'DD'

    def __unicode__(self):
        return self.name

class Quota(models.Model):
    """
    Represents a quota upgrade for a user shell account
    """
    user = models.ForeignKey(User)
    quantity = models.IntegerField(help_text="How many quota upgrades to order")
    quota_size = models.IntegerField(default=QUOTA_INC,help_text="How much each upgrade is worth")
    status = models.CharField(max_length=2,choices=QUOTA_STATUS)
    date = models.DateTimeField(help_text="The date of the original request")

    def __unicode__(self):
        return str(self.quantity) + " for " + self.user.username + ", currently " + self.status

class MailingList(models.Model):
    """
    Represents the info for mailman mailing lists in
    the reinhardt database, also acts as a proxy
    to update the mailman database
    """
    users = models.ManyToManyField(User, blank=True)
    list = models.CharField(max_length=30, unique=True)

    def export_to_mailman(self):
        """
        Convenience method used when you want to push all
        the users for this MailingList to its respective
        mailman list
        """
        try:
            for user in self.users():
                subscribe_member(user, self)
        except MailmanError: pass

    def clear_mailman_list(self):
        """
        Unsubscribes everyone from the mailman list
        """
        pass

    def import_from_mailman(self):
        """
        This clears this mailing list and adds all the
        members who are subscribed in the mailman database
        """
        pass

    def __unicode__(self):
        return self.list


def ensure_memberinfo_callback(sender, instance, **kwargs):
    """
    Used to create a Member object for any user that doesn't
    have it when saving the User, for sanity.
    """
    profile, new = Member.objects.get_or_create(user=instance)

post_save.connect(ensure_memberinfo_callback, sender=User)

class ExecPosition(models.Model):
    """
    Represents an exec position
    """
    title = models.CharField(max_length=30)

    class Meta:
        ordering = ['title']

    def __unicode__(self):
        return self.title

class ExecPlacement(models.Model):
    """
    Represents a time period of working on the exec
    """
    position = models.ForeignKey(ExecPosition)
    user = models.ForeignKey(User)
    start = models.DateField()
    end = models.DateField()

    class Meta:
        ordering = ['start']

    def __unicode__(self):
        return "%s/%s - %s" % (self.start.year, self.end.year, self.position)

class Society(User):
    """
    A society is just a User which also has a related
    user who is responsible for it

    what should it's first and last name be? blank and blank?
    """
    representative = models.ForeignKey(User, related_name="represented_societies")

    class Meta:
        verbose_name_plural = "Societies"

post_save.connect(ensure_memberinfo_callback, sender=Society)
