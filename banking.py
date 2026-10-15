"""Character-owned gold accounts; commands never accept another account ID."""
import re
import uuid


class Banking:
    def init_banking(self):
        self.state.setdefault('bank_accounts', {})
        if self.p:
            self.p.setdefault('id', 'player-'+uuid.uuid4().hex)

    def bank_balance(self):
        return self.state['bank_accounts'].get(self.p['id'], 0)

    def bank_command(self, verb, target):
        if not self.w['rooms'][self.p['room']].get('bank_service'):
            raise ValueError('Visit the bank to check your account, deposit or withdraw gold.')
        if self.p['combat']:
            raise ValueError('Finish the fight before banking.')
        if verb in ('bank', 'balance'):
            if target not in ('', 'balance'):
                raise ValueError('Use BALANCE, DEPOSIT <amount or ALL>, or WITHDRAW <amount or ALL>.')
            self.log(f'Your bank account holds {self.bank_balance()} gold. You carry {self.p["gold"]} gold. '
                     'DEPOSIT <amount or ALL>; WITHDRAW <amount or ALL>. Only you can withdraw from this account.')
            return
        available = self.p['gold'] if verb == 'deposit' else self.bank_balance()
        if target in ('all', 'all gold'):
            amount = available
        elif re.fullmatch(r'[0-9]+(?: gold)?', target):
            amount = int(target.split()[0])
        else:
            raise ValueError(f'Use {verb.upper()} followed by a positive whole amount or ALL.')
        if amount <= 0:
            raise ValueError('There is no gold to transfer. Enter a positive whole amount.')
        if amount > available:
            raise ValueError('You do not carry that much gold.' if verb == 'deposit' else 'Your own account does not contain that much gold.')
        direction = 1 if verb == 'deposit' else -1
        self.state['bank_accounts'][self.p['id']] = self.bank_balance()+direction*amount
        self.p['gold'] -= direction*amount
        self.log(f'{"Deposited" if verb == "deposit" else "Withdrew"} {amount} gold. '
                 f'Your bank balance is {self.bank_balance()} gold; you carry {self.p["gold"]} gold.', 'reward')

    def extra_command(self, verb, target):
        if verb in ('bank', 'balance', 'deposit', 'withdraw'):
            self.bank_command(verb, target); return True
        return super().extra_command(verb, target)

    def extra_snapshot(self, result):
        result = super().extra_snapshot(result)
        if self.p:
            result['player']['bank_gold'] = self.bank_balance()
            result['room']['bank_service'] = bool(self.w['rooms'][self.p['room']].get('bank_service'))
        return result
