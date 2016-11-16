import sys
sys.path.append("./")
import codecs
import json
import numpy as np
# from model_trainer.cnn_implicit_classifier import cnn_config
# from model_trainer.cnn_implicit_classifier import evaluation
import cnn_config
import evaluation
import sys
import math

from keras.models import Graph
from keras.layers.core import Dense, Activation, Flatten,Dropout,Reshape
from keras.layers.convolutional import Convolution1D, MaxPooling1D
from keras.preprocessing import sequence
from keras.layers.embeddings import Embedding
from keras.optimizers import Adagrad
from gensim.models import Word2Vec
from keras.preprocessing.text import text_to_word_sequence,base_filter
from keras.utils import np_utils
from keras.utils.np_utils import accuracy
from keras.callbacks import Callback,EarlyStopping
from keras import backend as K
from confusion_matrix import Alphabet

def pretainning():
    threshold_vocab = 0
    ndims = 300
    pos_ndims = 50
    maxlen = 80
    trian_file_path = "../../data/conll16st-en-01-12-16-train/"
    dev_file_path = "../../data/conll16st-en-01-12-16-dev/"
    parses_file_name = "parses.json"
    relations_file_name = "relations.json"
    train_parses = trian_file_path + parses_file_name
    dev_parses = dev_file_path + parses_file_name
    train_relations = trian_file_path + relations_file_name
    dev_relations = dev_file_path + relations_file_name
    vocab = set()
    pos_vocab = set()
    w2i_dic = {}
    p2i_dic = {}
    w2v_file = "../../../../GoogleNews-vectors-negative300.bin"
    wv = Word2Vec.load_word2vec_format(w2v_file, binary=True)

    def data_process(relations_file,parses_file):
        rf = open(relations_file)
        pf = open(parses_file)
        relations = [json.loads(x) for x in rf]
        parse_dict = json.load(codecs.open(parses_file, encoding='utf8'))
        relation = []
        flag= 0
        for r in relations:
            docid = r['DocID']
            type = r['Type']
            sense = r['Sense']
            if type == 'Explicit':
                continue
            ''' arg_offset_list = [sentence_index,wordinsentence_index] from TokenList in relations '''
            arg1_tokenlist = [[t[3],t[4]] for t in r['Arg1']['TokenList']]
            arg2_tokenlist = [[t[3],t[4]] for t in r['Arg2']['TokenList']]
            arg1_word = [parse_dict[docid]["sentences"][sent_index]["words"][word_index][0] for sent_index,word_index in arg1_tokenlist]
            arg1_pos = [parse_dict[docid]["sentences"][sent_index]["words"][word_index][1]["PartOfSpeech"] for sent_index,word_index in arg1_tokenlist]
            arg2_word = [parse_dict[docid]["sentences"][sent_index]["words"][word_index][0] for sent_index,word_index in arg2_tokenlist]
            arg2_pos = [parse_dict[docid]["sentences"][sent_index]["words"][word_index][1]["PartOfSpeech"] for sent_index,word_index in arg2_tokenlist]
            relation.append((arg1_word,arg2_word,arg1_pos,arg2_pos,sense,docid))
        return relation

    def vocab_process():
        count = {}
        relation = data_process(train_relations,train_parses)
        for x in relation:
            for w in x[0]+x[1]:
                if w in count.keys():
                    count[w] += 1
                else:
                    count[w] = 1
        for x in relation:
            for w in x[0]+x[1]:
                if w in count.keys():
                    if count[w] > threshold_vocab:
                        vocab.add(w)
            for p in x[2]+x[3]:
                pos_vocab.add(p)


    def WE_process():
        vocab_process()
        idx = 1  # o for unknown
        for w in vocab:
            w2i_dic[w] = idx
            idx += 1
        WE = np.zeros((len(vocab) + 1, ndims), dtype='float32')
        pos_WE = np.zeros((len(pos_vocab) + 1, pos_ndims), dtype='float32')
        pre_trained = set(wv.vocab.keys())
        WE[0, :] = np.array(np.random.uniform(-0.5 / ndims, 0.5 / ndims, (ndims,)), dtype='float32')
        pos_WE[0, :] = np.array(np.random.uniform(-0.5 / pos_ndims, 0.5 / pos_ndims, (pos_ndims,)), dtype='float32')
        for x in vocab:
            if x in pre_trained:
                WE[w2i_dic[x], :] = wv[x]
            else:
                WE[w2i_dic[x], :] = np.array(np.random.uniform(-0.5 / ndims, 0.5 / ndims, (ndims,)),
                                             dtype='float32')  # hyperparameter
        for i, y in enumerate(pos_vocab,start=1):
            p2i_dic[y] = i
            pos_WE[i, :] = np.array(np.random.uniform(-0.5 / pos_ndims, 0.5 / pos_ndims, (pos_ndims,)), dtype='float32')
        dstr = json.dumps([w2i_dic, p2i_dic])
        f = open("all_vocab_dict.txt",'w')
        f.write(dstr)
        f.close()
        return WE, pos_WE

    def embedding_process(train_relations,train_parses):
        data = data_process(train_relations,train_parses)
        tmp = []
        for x in data:
            arg1 = []
            arg2 = []
            pos1 = []
            pos2 = []
            sense = []
            type = []
            for w in x[0]:
                if w in w2i_dic.keys():
                    arg1.append(w2i_dic[w])
                else:
                    arg1.append(0)
            for w in x[1]:
                if w in w2i_dic.keys():
                    arg2.append(w2i_dic[w])
                else:
                    arg2.append(0)
            for w in x[2]:
                if w in p2i_dic.keys():
                    pos1.append(p2i_dic[w])
                else:
                    pos1.append(0)
            for w in x[3]:
                if w in p2i_dic.keys():
                    pos2.append(p2i_dic[w])
                else:
                    pos2.append(0)
            s = x[4][0]
            sense.append(cnn_config.Sense_To_Label[s])
            type.append(cnn_config.Type_To_Label[s])
            tmp.append((arg1, arg2, pos1, pos2, sense, type))
        data = tmp
        X_1 = np.array([x[0] for x in data])
        X_2 = np.array([x[1] for x in data])
        X_pos_1 = np.array([x[2] for x in data])
        X_pos_2 = np.array([x[3] for x in data])
        y_s = np_utils.to_categorical(np.array([x[4] for x in data]))
        y_t = np_utils.to_categorical(np.array([x[5] for x in data]))
        X_1 = sequence.pad_sequences(X_1, maxlen=maxlen, padding='pre', truncating='pre')
        X_2 = sequence.pad_sequences(X_2, maxlen=maxlen, padding='post', truncating='post')
        X_pos_1 = sequence.pad_sequences(X_pos_1, maxlen=maxlen, padding='pre', truncating='pre')
        X_pos_2 = sequence.pad_sequences(X_pos_2, maxlen=maxlen, padding='post', truncating='post')
        print(train_relations,train_parses, (X_1.shape, X_pos_1.shape, y_s.shape, y_t.shape))
        return (X_1, X_2, X_pos_1, X_pos_2, y_s, y_t)

    WE, pos_WE = WE_process()
    X_train_1, X_train_2, X_train_pos_1, X_train_pos_2, y_train, y_train_type = embedding_process(train_relations,train_parses)
    X_dev_1, X_dev_2, X_dev_pos_1, X_dev_pos_2, y_dev, y_dev_type = embedding_process(dev_relations,dev_parses)
    print("the lens of vocab and pos_vocab: ",len(vocab),len(pos_vocab))
    return (WE, pos_WE, len(vocab), len(pos_vocab),
            X_train_1, X_train_2, X_train_pos_1, X_train_pos_2, y_train, y_train_type,
            X_dev_1, X_dev_2, X_dev_pos_1, X_dev_pos_2, y_dev, y_dev_type)

def build_model(lr, activation, nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,
          WE=None, pos_WE=None, word_dim=35397, pos_dim=45,train=True):

    ndims = 300
    pos_ndims = 50
    pool_length = 80
    maxlen = 80

    model = Graph()
    model.add_input(name='arg1', input_shape=(maxlen,), dtype=int)
    model.add_input(name='arg2', input_shape=(maxlen,), dtype=int)
    model.add_input(name='pos1', input_shape=(maxlen,), dtype=int)
    model.add_input(name='pos2', input_shape=(maxlen,), dtype=int)

    # our vocab indices into embedding_dims dimensions
    if (WE is not None):
        model.add_node(
            Embedding(input_dim=word_dim + 1, input_length=maxlen, weights=[WE], output_dim=ndims, mask_zero=True),
            name='embedding1', input='arg1')
        model.add_node(
            Embedding(input_dim=word_dim + 1, input_length=maxlen, weights=[WE], output_dim=ndims, mask_zero=True),
            name='embedding2', input='arg2')
        model.add_node(
            Embedding(input_dim=pos_dim + 1, input_length=maxlen, weights=[pos_WE], output_dim=pos_ndims, mask_zero=True),
            name='embedding3', input='pos1')
        model.add_node(
            Embedding(input_dim=pos_dim + 1, input_length=maxlen, weights=[pos_WE], output_dim=pos_ndims, mask_zero=True),
            name='embedding4', input='pos2')
    else:
        model.add_node(
        Embedding(input_dim=word_dim + 1, input_length=maxlen, output_dim=ndims, mask_zero=True),
        name='embedding1', input='arg1')
        model.add_node(
            Embedding(input_dim=word_dim + 1, input_length=maxlen, output_dim=ndims, mask_zero=True),
            name='embedding2', input='arg2')
        model.add_node(
            Embedding(input_dim=pos_dim + 1, input_length=maxlen, output_dim=pos_ndims, mask_zero=True),
            name='embedding3', input='pos1')
        model.add_node(
            Embedding(input_dim=pos_dim + 1, input_length=maxlen,  output_dim=pos_ndims, mask_zero=True),
            name='embedding4', input='pos2')
    model.add_node(Dropout(0.25), merge_mode='concat', concat_axis=2, name='arg_1', inputs=['embedding1', 'embedding3'])
    model.add_node(Dropout(0.25), merge_mode='concat', concat_axis=2, name='arg_2', inputs=['embedding2', 'embedding4'])

    model.add_shared_node(Convolution1D(nb_filter=nb_filter1,
                                        filter_length=filter_length1,
                                        border_mode='same',
                                        activation=activation,
                                        subsample_length=1), inputs=['arg_1', 'arg_2'], name='cnn1',
                          merge_mode='concat')

    model.add_shared_node(Convolution1D(nb_filter=nb_filter2,
                                        filter_length=filter_length2,
                                        border_mode='same',
                                        activation=activation,
                                        subsample_length=1), inputs=['arg_1', 'arg_2'], name='cnn2',
                          merge_mode='concat')

    model.add_shared_node(Convolution1D(nb_filter=nb_filter3,
                                        filter_length=filter_length3,
                                        border_mode='same',
                                        activation=activation,
                                        subsample_length=1), inputs=['arg_1', 'arg_2'], name='cnn3',
                          merge_mode='concat')
    # we use standard max pooling (halving the output of the previous layer):

    model.add_node(MaxPooling1D(pool_length=pool_length), name='mpooling1', input='cnn1')
    model.add_node(MaxPooling1D(pool_length=pool_length), name='mpooling2', input='cnn2')
    model.add_node(MaxPooling1D(pool_length=pool_length), name='mpooling3', input='cnn3')
    model.add_node(Flatten(), name='f1', input='mpooling1')
    model.add_node(Flatten(), name='f2', input='mpooling2')
    model.add_node(Flatten(), name='f3', input='mpooling3')

    model.add_node(Dense(20),name='final', inputs=['f1','f2','f3'],merge_mode='concat')
    model.add_node(Activation('softmax'),name='lastDim',input='final')
    model.add_output(name='output', input = 'lastDim')

    ada = Adagrad(lr=lr, epsilon=1e-06)
    model.compile(optimizer=ada, loss={'output':'categorical_crossentropy'})
    model.summary()
    # if train:
    #     json_string = model.to_json()
    #     open('1-2-5_1024_weights.h5', 'w').write(json_string)
    return model

def fit_model(lr, activation, nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,
              WE, pos_WE, word_dim, pos_dim,
              X_train_1, X_train_2, X_train_pos_1, X_train_pos_2, y_train, y_train_type,
              X_dev_1, X_dev_2, X_dev_pos_1, X_dev_pos_2, y_dev, y_dev_type,train=True):
    batch_size = 64
    nb_epoch = 80
    # callback each epoch:
    class scorer(Callback):
        best_acc = 0
        best_epoch_th = 0
        dev_best_acc = 0
        dev_epoch_th = 0
        def on_epoch_end(self, epoch, logs={}):
            dev_output = model.predict({'arg1': X_dev_1, 'arg2': X_dev_2, 'pos1': X_dev_pos_1, 'pos2': X_dev_pos_2},
                                       batch_size=batch_size)['output']
            acc_dev = (len([1 for i in range(len(y_dev)) if (TMP_equal_array(TMP_to_one(dev_output[i]),y_dev[i]))])) / len(y_dev)
            sys.stdout.flush()
            print()
            print('Dev accuracy is:', round(acc_dev, 4), " at ", epoch)
            if acc_dev > scorer.dev_best_acc:
                scorer.dev_best_acc = np.round(acc_dev, 4)
                scorer.dev_epoch_th = epoch + 1
                print("saving the best model-----the best dev is: ",scorer.dev_best_acc)
                model.save_weights('imp_weights.h5' ,overwrite=True)
            if epoch % 3 == 0:
                print('the best dev is imp_weights.h5:',nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3, 'epoch', scorer.dev_epoch_th, 'dev_best_acc:', scorer.dev_best_acc)
            print()
            sys.stdout.flush()
        def on_train_end(self, logs={}):
            print('the final best dev is:', 'dev_epoch', nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,scorer.dev_epoch_th, 'dev_best_acc:', scorer.dev_best_acc)
    scorer = scorer()
    stop = EarlyStopping(patience=10, verbose=1)
    print('Train...')
    model = build_model(lr, activation, nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,
              WE, pos_WE, word_dim, pos_dim,train=True,)
    model.fit({'arg1': X_train_1, 'arg2': X_train_2, 'pos1': X_train_pos_1, 'pos2': X_train_pos_2,
               'output': y_train}, callbacks = [scorer, stop],
              batch_size = batch_size, shuffle = True,
              nb_epoch = nb_epoch, validation_data = (
        {'arg1': X_dev_1, 'arg2': X_dev_2, 'pos1': X_dev_pos_1, 'pos2': X_dev_pos_2,
         'output': y_dev}))

    best_acc_test = scorer.best_acc
    best_epoch = scorer.best_epoch_th
    dev_best_acc = scorer.dev_best_acc
    dev_epoch_th = scorer.dev_epoch_th
    return (best_epoch, best_acc_test, dev_epoch_th, dev_best_acc)

def onehot2num(y):
        y_num=[]
        y_sense=[]
        for x in y:
            index=22
            for i in range(len(x)):
                if x[i]==1:
                    index=i
                    continue
            if index==22:
                print (x)
            sense = cnn_config.Label_To_Sense[index]
            y_num.append(index)
            y_sense.append(sense)
        return y_num,y_sense

def TMP_equal_array(x,y):
    #print("x:",x,"||y:",y)
    if len(x) != len(y):
        return False
    for i in range(len(x)):
        if x[i] != y[i]:
            return False
    return True

def TMP_to_one(x):
    index = np.argmax(x)
    # print(x,index)
    ret = [0. for i in range(len(x))]
    ret[index] = 1.
    return ret

def evaluate(x,y):
    temp=[]
    for t in y:
        temp.append(TMP_to_one(t))
    y = temp
    gold_num_list,gold_sense_list = onehot2num(x)
    pred_num_list,pred_sense_list = onehot2num(y)

    alphabet = Alphabet()
    for s in cnn_config.Label_To_Sense.values():
        alphabet.add(s)
    cm = evaluation.compute_binary_eval_metric(pred_sense_list, gold_sense_list, alphabet)
    precision, recall, f1  = cm.compute_average_prf()
    return precision,recall,f1

def test(lr, activation, nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,
          WE, pos_WE, word_dim, pos_dim,batch_size,train):
    model = build_model(lr, activation, nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,
          WE, pos_WE, word_dim, pos_dim,train)
    model.load_weights('imp_weights.h5')
    dev_output = model.predict({'arg1': X_dev_1, 'arg2': X_dev_2, 'pos1': X_dev_pos_1, 'pos2': X_dev_pos_2},
                                       batch_size=batch_size)['output']
    acc_dev = (len([1 for i in range(len(y_dev)) if (TMP_equal_array(TMP_to_one(dev_output[i]),y_dev[i]))])) / len(y_dev)
    print()
    print("dev accurary is: ",acc_dev)

if __name__ == '__main__':

    WE, pos_WE, word_dim, pos_dim, \
    X_train_1, X_train_2, X_train_pos_1, X_train_pos_2, y_train, y_train_type, \
    X_dev_1, X_dev_2, X_dev_pos_1, X_dev_pos_2, y_dev, y_dev_type = pretainning()
    activation = "tanh"
    batch_size = 64
    lr = 0.001
    final = []
    result = []
    i=0
    # nb_filter, filter_length1, filter_length2, filter_length3 = 1024,3,3,3
    nb_filter = [(500,400,300),(600,500,400),(200,100,50),(200,200,100),(100,50,20)]
    filter_list = [(3,4,5),(5,6,7),(2,6,12),(1,5,10),(4,7,11)]
    for nb,length in zip(nb_filter,filter_list):
        nb_filter1,nb_filter2,nb_filter3 = nb
        filter_length1, filter_length2, filter_length3 = length
        '''  train '''
        best_epoch, best_acc_test, dev_epoch_th, dev_best_acc = \
                fit_model(
                    lr, activation, nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,
                  WE, pos_WE, word_dim, pos_dim,
                  X_train_1, X_train_2, X_train_pos_1, X_train_pos_2, y_train, y_train_type,
                  X_dev_1, X_dev_2, X_dev_pos_1, X_dev_pos_2, y_dev, y_dev_type,train=True)
        print(best_epoch, best_acc_test, dev_epoch_th, dev_best_acc)
        print('the final results is : ',nb_filter1,nb_filter2,nb_filter3,  filter_length1, filter_length2, filter_length3,dev_best_acc)
        final.append((nb_filter1,nb_filter2,nb_filter3, filter_length1, filter_length2, filter_length3,dev_best_acc))
        result.append(np.round(dev_best_acc,4))
        print(i)
        print(final)
        print(result)
    # '''  test '''
    # test(lr, activation, nb_filter, filter_length1, filter_length2, filter_length3,
    # WE, pos_WE, word_dim, pos_dim,batch_size,train=False)


