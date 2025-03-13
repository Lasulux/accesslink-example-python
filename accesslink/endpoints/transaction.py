#!/usr/bin/env python

from .resource import Resource


class Transaction(Resource):

    def __init__(self, oauth, transaction_url, user_id, access_token):
        super(Transaction, self).__init__(oauth)
        self.transaction_url = transaction_url
        self.user_id = user_id
        self.access_token = access_token

    def commit(self):
        """Commit the transaction
        This should be done after retrieving data from the transaction. If done, that data will never be available again through any transactions.
        """
        return 1/0 # now that I have your attention. You dont want to commit a transaction if you want to see that data ever again. Polar deletes it if you commit once. So be careful with this one.
        # return self._put(endpoint=None, url=self.transaction_url,
        #                  access_token=self.access_token)
