    
Using the API
-------------

The API is an independient piece of code which you could use for your project
or use interactively. For example ::

    >>> from cuevanalinks import cuevanaapi
    >>> api = cuevanaapi.CuevanaAPI ()
    >>> house = api.get_show ('house')
    >>> house.plot
    u'El doctor Gregory House, especialista en el tratamiento de enfermedades infecciosas, trabaja en un hospital universitario de Princetown, donde dirige una unidad especial encargada de pacientes afectados por dolencias extrañas y en la que colabora con un selecto grupo de aventajados ayudantes.'
    >>> house7x1 = house.get_episode (7, 1)
    >>> house7x1.title
    'Now What?'
    >>> house7x1.cast
    ['Hugh Laurie',
    'Lisa Edelstein',
    'Omar Epps',
    'Jesse Spencer',
    'Jennifer Morrison',
    'Robert Sean Leonard',
    'Olivia Wilde',
    'Peter Jacobson']
    >>> house7x1.sources
    ['http://www.megaupload.com/?d=DM58TA0J',
    'http://www.filesonic.com/file/36841721/?',
    'http://bitshare.com/?f=67z435xm',
    'http://www.filefactory.com/file/caf85b9']
    >>> house7x1.subs
    {'ES': 'http://www.cuevana.tv/download_sub?file=s/sub/7888_ES.srt'}


API reference
-------------

.. automodule:: cuevanalinks.cuevanaapi
   :members:
   :undoc-members: 
