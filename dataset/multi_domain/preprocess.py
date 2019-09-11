import json
import sys
import os
mode = 'cased'
zs_flag = False

digit_map = {
             '0': 'zero',
             '1': 'one',
             '2': 'two',
             '3': 'three',
             '4': 'four',
             '5': 'five',
             '6': 'six',
             '7': 'seven',
             '8': 'eight',
             '9': 'nine',
             '10': 'ten'}

def get_data(path):
    all_service = set()

    schemas = json.load(open(path+os.sep+'schema.json', 'r'))

    data = []

    data_categoricals = []

    services = dict()

    sample_count = 0
    neg_sample_count = 0
    categorical_sample_count = 0
    dc_count = 0
    for schema in schemas:
        service_name = schema['service_name']
        services[service_name] = dict()
        service = services[service_name]
        service_desc = schema['description'].lower()
        slots = schema['slots']

        service['desc'] = service_desc

        service['slots'] = dict()
        for slot in slots:
            name = slot['name']
            description = slot['description'].lower()
            is_categorical = slot['is_categorical']
            possible_values = slot['possible_values']
            service['slots'][name] = dict({'desc':description,
                                           'is_categorical': is_categorical,
                                           'possible_values':possible_values
                                           })

        intents = schema['intents']
        service['intents'] = dict()
        for intent in intents:
            name = intent['name']
            description = intent['description'].lower()
            is_transactional = intent['is_transactional']
            required_slots = intent['required_slots']
            optional_slots = intent['optional_slots']
            service['intents'][name] = dict({'desc':description,
                                             'is_transactional': is_transactional,
                                             'required_slots': required_slots,
                                             'optional_slots': optional_slots
                                             })
    for file in os.listdir(path):
        if not file.find('schema')>=0:
            dialogues = json.load(open(path+os.sep+file, 'r'))
        else:
            continue
        for dialogue in dialogues:
            data_categorical = []
            active_services = dialogue['services']
            for service in services:
                all_service.add(service)
            if not active_services[0] in services:
                continue
            dial_id = dialogue['dialogue_id']
            uttrs = []
            tagging_values = []
            value_offset = dict()
            acc_len = 0
            tc = 0
            history_slot_val = dict()
            dial_data = []
            for sev in active_services:
                history_slot_val[sev] = dict()
            for turn in dialogue['turns']:
                tc += 1
                uttr = turn['utterance']
                uttrs.append(uttr)
                context = ' ; '.join(uttrs)
                frames = turn['frames']
                speaker = turn["speaker"]
                turn_data = []
                for frame in frames:
                    # slot tagging
                    slots = frame['slots']
                    for slot in slots:
                        slot_name = slot['slot']
                        start_offset = slot['start']
                        end_offset = slot['exclusive_end']
                        value = uttr[start_offset:end_offset]
                        tagging_values.append(value)
                        if not value in value_offset: value_offset[value] = []
                        value_offset[value].append([acc_len + start_offset, acc_len + end_offset - 1])

                    service_name = frame['service']
                    if speaker == 'USER':
                        state = frame['state']
                        active_intent = state["active_intent"]
                        if not active_intent == 'NONE':
                            intent_desc = services[service_name]['intents'][active_intent]['desc']
                        else:
                            intent_desc = 'none'

                        slot_val = state['slot_values']

                        for slot_name, vals in slot_val.items():

                            slot_desc = services[service_name]['slots'][slot_name]['desc']
                            is_categorical = services[service_name]['slots'][slot_name]['is_categorical']
                            i = -1
                            for _, val in enumerate(vals):
                                # if val == 'dontcare':
                                #     dc_count += 1
                                #     continue
                                if not is_categorical:
                                    if not val in tagging_values and not val == 'dontcare':
                                        continue
                                    if not val == 'dontcare':
                                        start_idx, end_idx = value_offset[val][-1]
                                        assert context[start_idx:end_idx+1] == val
                                    i += 1
                                    if i == 0:
                                        if val == 'dontcare':
                                            turn_data.append({
                                                         "question": "what is the %s of %s?" % (slot_desc, intent_desc),
                                                         "is_categorical": False,
                                                         "intent": active_intent,
                                                         "intent_desc": intent_desc,
                                                         "service": service_name,
                                                         "slot": slot_name,
                                                         "slot_desc": slot_desc,
                                                         "answers": [{
                                                             "text": val.lower() if mode=='uncased' else val,
                                                             "start_idx": -1
                                                         }]
                                                              })
                                        else:
                                            turn_data.append({
                                                         "question": "what is the %s of %s?" % (slot_desc, intent_desc),
                                                         "is_categorical": False,
                                                         "intent": active_intent,
                                                         "intent_desc": intent_desc,
                                                         "service": service_name,
                                                         "slot": slot_name,
                                                         "slot_desc": slot_desc,
                                                         "answers": [{
                                                             "text": val.lower() if mode=='uncased' else val,
                                                             "start_idx": start_idx
                                                         }]
                                                              })
                                    else:
                                        turn_data[-1]['answers'].append({
                                            "text": val.lower() if mode == 'uncased' else val,
                                            "start_idx": start_idx
                                        })
                                    sample_count += 1
                                else:
                                    pv = services[service_name]['slots'][slot_name]['possible_values'] + ['dontcare']

                                    # if '1' in pv or '2' in pv:
                                    #     cands = ["the %s of %s is %s" % (slot_desc, intent_desc, v) for v in pv] + ["the %s of %s is %s" % (slot_desc, intent_desc, digit_map[v]) for v in pv]
                                    #     ids = [pv.index(val), pv.index(val) + len(pv)]
                                    #     answer = [val, digit_map[val]]
                                    # else:
                                    cands = ["the %s of %s is %s" % (slot_desc, intent_desc, v) for v in pv]
                                    ids = [pv.index(val)]
                                    answer = [val]

                                    turn_data.append({
                                        "text_id": dial_id + ":" + str(tc),
                                        "is_categorical": True,
                                        "intent": active_intent,
                                        "intent_desc": intent_desc,
                                        "slot": slot_name,
                                        "slot_desc": slot_desc,
                                        "service": service_name,
                                        "candidate_answers": cands,
                                        "true_ids": ids,
                                        'answer': answer
                                    }
                                    )
                                    categorical_sample_count += len(pv) + 1
                        if not active_intent == 'NONE':
                            for st in ['required_slots', 'optional_slots']:
                                for neg_slot in services[service_name]['intents'][active_intent][st]:
                                    if not neg_slot in slot_val:
                                        neg_sample_count += 1
                                        if not services[service_name]['slots'][neg_slot]['is_categorical']:
                                            turn_data.append({
                                                         "question": "what is the %s of %s?" % (services[service_name]['slots'][neg_slot]['desc'], intent_desc),
                                                         "is_categorical": False,
                                                         "intent": active_intent,
                                                         "slot": neg_slot,
                                                         "intent_desc": intent_desc,
                                                         "slot_desc": services[service_name]['slots'][neg_slot]['desc'],
                                                         "service": service_name,
                                                         "answers": [{
                                                             "text": "",
                                                             "start_idx": -1
                                                         }]})
                                        else:
                                            pv = services[service_name]['slots'][neg_slot]['possible_values']
                                            slot_desc = services[service_name]['slots'][neg_slot]['desc']
                                            if '1' in pv or '2' in pv:
                                                cands = ["the %s of %s is %s" % (slot_desc, intent_desc, v) for v in pv] + ["the %s of %s is %s" % (slot_desc, intent_desc, digit_map[v]) for v in pv]
                                                ids = [-1]
                                                answer = ['']
                                            else:
                                                cands = ["the %s of %s is %s" % (slot_desc, intent_desc, v) for v in pv]
                                                ids = [-1]
                                                answer = ['']
                                            turn_data.append({
                                                         "question": "what is the %s of %s?" % (services[service_name]['slots'][neg_slot]['desc'], intent_desc),
                                                         "is_categorical": True,
                                                         "intent": active_intent,
                                                         "intent_desc": intent_desc,
                                                         "slot": neg_slot,
                                                         "service": service_name,
                                                         "slot_desc": slot_desc,
                                                         "candidate_answers": cands,
                                                         "true_ids": ids,
                                                         "answer": answer})
                    else:
                        action = frame['actions']
                if speaker == 'USER':
                    dial_data.append({
                        "text_id": dial_id + ":" + str(tc),
                        "active_service": active_services,
                        "context": ' ; '.join(uttrs[-2:]).lower() if mode == 'uncased' else ' ; '.join(uttrs[-2:]),
                        'qa': turn_data}
                    )
                acc_len += len(uttr) + 3
            data.append(dial_data)
    print(dc_count)
    return data, all_service
    # cc = 0
    # if ' '.join(active_services).find('Restaurant')>=0:
    #     cc += 1
    #     data_res.append(dial_data)
    # elif ' '.join(active_services).find('Movie')>=0:
    #     cc += 1
    #     data_mov.append(dial_data)
    # elif ' '.join(active_services).find('Hotels_1')>=0 or ' '.join(active_services).find('Hotels_2')>=0:
    #     cc += 1
    #     data_hotel.append(dial_data)
    # else:
    #     cc += 1
    #     data_other.append(dial_data)
    # assert cc == 1


train_data, train_service = get_data('train')
test_data, test_service = get_data('dev')

indomain_service = []
outdomain_service = []
sup_service = []
for s1 in test_service:
    f1 = False
    f2 = False
    for s2 in train_service:
        if s1 == s2:
            f1 = True
        if s1.split('_')[0] == s2.split('_')[0]:
            f2 = True
    if f1:
        sup_service.append(s1)
    elif f2:
        indomain_service.append(s1)
    else:
        outdomain_service.append(s1)


c1 = 0
c2 = 0
c3 = 0
sup_data = []
ind_data = []
oud_data = []
for dial_data in test_data:
    for serv in dial_data[0]["active_service"]:
        if serv in sup_service:
            sup_data.append(dial_data)
        if serv in indomain_service:
            ind_data.append(dial_data)
        if serv in outdomain_service:
            oud_data.append(dial_data)
    # for data in dial_data:
    #     for d in data['qa']:
    #         if d['service'] in sup_service:
    #             c1 += 1
    #         if d['service'] in indomain_service:
    #             c2 += 1
    #         if d['service'] in outdomain_service:
    #             c3 += 1
#print(c1, c2, c3)
print(sup_service)
print(indomain_service)
print(outdomain_service)
json.dump(train_data, open('examples_all_train.json', 'w'), indent=4)
json.dump(test_data, open('examples_all_test.json', 'w'), indent=4)
json.dump(sup_data, open('examples_sup_test.json', 'w'), indent=4)
json.dump(ind_data, open('examples_ind_test.json', 'w'), indent=4)
json.dump(oud_data, open('examples_oud_test.json', 'w'), indent=4)