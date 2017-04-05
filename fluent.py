#!/usr/bin/env python3
# encoding: utf8
# license: ISC (MIT/BSD compatible) https://choosealicense.com/licenses/isc/

# This library is principally created for python 3. However python 2 support may be doable and is welcomed.

"""Future Ideas:

# TODO consider numeric type to do stuff like wrap(3).times(...)
    or wrap([1,2,3]).call(len).times(yank_me)

Rework _.each.call.foo(bar) so 'call' is no longer a used-up symbol on each.
Also _.each.call.method(...) has a somewhat different meaning as the .call method on callable
could _.each.method(_, ...) work when auto currying is enabled?

Rework fluent so explicit unwrapping is required to do anythign with wrapped objects. 
(Basically calling ._ at the end)
The idea here is that this would likely enable the library to be used in big / bigger 
projects as it looses it's virus like qualities.
* Maybe this is best done as a separate import?
* This would also be a chance to consider always using the iterator versions of 
  all the collection methods under their original name and automatically unpacking 
  / triggering the iteration on ._? Not sure that's a great idea, as getting the 
  iterator to abstract over it is a) great and b) triggering the iteration is also 
  hard see e.g. groupby.
* This would require carefull analysis where wrapped objects are handed out as arguments
  to called methods e.g. .tee(). Also requires __repr__ and __str__ implementations that
  make sense.

Roundable (for all numeric needs?)
    round, times, repeat, if_true, if_false, else_

if_true, etc. are pretty much like conditional versions of .tee() I guess.

.if_true(function_to_call).else_(other_function_to_call)

consider to make chain/previous/unwrap functions for similarity with the other stuff

solve this inconsistency

>>> from fluent import *
>>> _([None]).pop()
fluent.wrap([])
>>> _([None]).pop().chain
[]
>>> _([None]).pop()
fluent.wrap([])
>>> _([1]).pop()
fluent.wrap(1)

"""

# REFACT rename wrap -> fluent? perhaps as an alias?
__all__ = [
    'wrap', # generic wrapper factory that returns the appropriate subclass in this package according to what is wrapped
    '_', # _ is an alias for wrap
    'lib', # wrapper for python import machinery, access every importable package / function directly on this via attribute access
]

import typing
import re
import math
import types
import functools
import itertools
import operator
import collections.abc

def wrap(wrapped, *, previous=None, chain=None):
    """Factory method, wraps anything and returns the appropriate Wrapper subclass.
    
    This is the main entry point into the fluent wonderland. Wrap something and 
    everything you call off of that will stay wrapped in the apropriate wrappers.
    """
    if isinstance(wrapped, Wrapper):
        return wrapped
    
    by_type = (
        (types.ModuleType, Module),
        (typing.Text, Text),
        (typing.Mapping, Mapping),
        (typing.AbstractSet, Set),
        (typing.Iterable, Iterable),
        (typing.Callable, Callable),
    )
    
    if wrapped is None and chain is None and previous is not None:
        chain = previous.chain
    
    decider = wrapped
    if wrapped is None and chain is not None:
        decider = chain
    
    for clazz, wrapper in by_type:
        if isinstance(decider, clazz):
            return wrapper(wrapped, previous=previous, chain=chain)
    
    return Wrapper(wrapped, previous=previous, chain=chain)

# sadly _ is pretty much the only valid python identifier that is sombolic and easy to type. Unicode would also be a candidate, but hard to type $, § like in js cannot be used
_ = wrap

def wrapped(wrapped_function, additional_result_wrapper=None, self_index=0):
    """
    Using these decorators will take care of unwrapping and rewrapping the target object.
    Thus all following code is written as if the methods live on the wrapped object
    
    Also perfect to adapt free functions as instance methods.
    """
    @functools.wraps(wrapped_function)
    def wrapper(self, *args, **kwargs):
        result = wrapped_function(*args[0:self_index], self.chain, *args[self_index:], **kwargs)
        if callable(additional_result_wrapper):
            result = additional_result_wrapper(result)
        return wrap(result, previous=self)
    return wrapper

def unwrapped(wrapped_function):
    """Like wrapped(), but doesn't wrap the result.
    
    Use this to adapt free functions that should not return a wrapped value"""
    @functools.wraps(wrapped_function)
    def forwarder(self, *args, **kwargs):
        return wrapped_function(self.chain, *args, **kwargs)
    return forwarder

def wrapped_forward(wrapped_function, additional_result_wrapper=None, self_index=1):
    """Forwards a call to a different object
    
    This makes its method available on the wrapper.
    This specifically models the case where the method forwarded to, 
    takes the current object as its first argument.
    
    This also deals nicely with methods that just live on the wrong object.
    """
    return wrapped(wrapped_function, additional_result_wrapper=additional_result_wrapper, self_index=self_index)

def tupleize(wrapped_function):
    """"Wrap the returned obect in a tuple to force execution of iterators.
    
    Especially usefull to de-iterate methods / function
    """
    @functools.wraps(wrapped_function)
    def wrapper(self, *args, **kwargs):
        return wrap(tuple(wrapped_function(self, *args, **kwargs)), previous=self)
    return wrapper

class Wrapper(object):
    """Universal wrapper.
    
    This class ensures that all function calls and attribute accesses 
    that can be caught in python will be wrapped with the wrapper again.
    
    This ensures that the fluent interface will persist and everything 
    that is returned is itself able to be chaned from again.
    
    Using this wrapper changes the behaviour of python soure code in quite a big way.
    
    a) If you wrap something, if you want to get at the real object from any 
       function call or attribute access off of that object, you will have to 
       explicitly unwrap it.
    
    b) All returned objects will be enhanced by behaviour that matches the 
       wrapped type. I.e. iterables will gain the collection interface, 
       mappings will gain the mapping interface, strings will gain the 
       string interface, etc.
    """
    
    def __init__(self, wrapped, *, previous, chain):
        assert wrapped is not None or chain is not None, 'Cannot chain off of None'
        self.__wrapped = wrapped
        self.__previous = previous
        self.__chain = chain
    
    # Proxied methods
    
    __getattr__ = wrapped(getattr)
    __getitem__ = wrapped(operator.getitem)
    
    def __str__(self):
        return "fluent.wrap(%s)" % self.chain
    
    def __repr__(self):
        return "fluent.wrap(%r)" % self.chain
    
    # REFACT consider wether I want to support all other operators too or wether explicit 
    # unwrapping is actually a better thing
    __eq__ = unwrapped(operator.eq)
    
    # Breakouts
    
    @property
    def unwrap(self):
        return self.__wrapped
    _ = unwrap # alias
    
    @property
    def previous(self):
        return self.__previous
    
    @property
    def chain(self):
        "Like .unwrap but handles chaining off of methods / functions that return None like SmallTalk does"
        if self.unwrap is not None:
            return self.unwrap
        return self.__chain
    
    # Utilities
    
    @wrapped
    def call(self, function, *args, **kwargs):
        "Call function with self as first argument"
        # Different from __call__! Calls function(self, …) instead of self(…)
        return function(self, *args, **kwargs)
    
    setattr = wrapped(setattr)
    getattr = wrapped(getattr)
    hasattr = wrapped(hasattr)
    delattr = wrapped(delattr)
    
    isinstance = wrapped(isinstance)
    issubclass = wrapped(issubclass)
    
    def tee(self, function):
        """Like tee on the shell
        
        Calls the argument function with self, but then discards the result and allows 
        further chaining from self."""
        function(self)
        return self
    
    dir = wrapped(dir)
    vars = wrapped(vars)

# REFACT consider to use wrap as the placeholder to have less symbols? Probably not worth it...
virtual_root_module = object()
class Module(Wrapper):
    """Importer shortcut.
    
    All attribute accesses to instances of this class are converted to
    an import statement, but as an expression that returns the wrapped imported object.
    
    Example:
    
    >>> lib.sys.stdin.read().map(print)
    
    Is equivalent to
    
    >>> import importlib
    >>> wrap(importlib.import_module('sys').stdin).read().map(print)
    
    But of course without creating the intermediate symbol 'stdin' in the current namespace.
    
    All objects returned from lib are pre-wrapped, so you can chain off of them immediately.
    """
    
    def __getattr__(self, name):
        if hasattr(self.chain, name):
            return wrap(getattr(self.chain, name))
        
        import importlib
        module = None
        if self.chain is virtual_root_module:
            module = importlib.import_module(name)
        else:
            module = importlib.import_module('.'.join((self.chain.__name__, name)))
        
        return wrap(module)

wrap.lib = lib = Module(virtual_root_module, previous=None, chain=None)

class Callable(Wrapper):
    
    def __call__(self, *args, **kwargs):
        """"Call through with a twist.
        
        If one of the args is `wrap` / `_`, then this acts as a shortcut to curry instead"""
        # REFACT consider to drop the auto curry - doesn't look like it is so super usefull
        # REFACT Consider how to expand this so every method in the library supports auto currying
        if wrap in args:
            return self.curry(*args, **kwargs)
        
        result = self.chain(*args, **kwargs)
        chain = None if self.previous is None else self.previous.chain
        return wrap(result, previous=self, chain=chain)
    
    # REFACT rename to partial for consistency with stdlib?
    # REFACT consider if there could be more utility in supporting placeholders for more usecases.
    # examples:
    #   Switching argument order?
    @wrapped
    def curry(self, *curry_args, **curry_kwargs):
        """"Like functools.partial, but with a twist.
        
        If you use `wrap` or `_` as a positional argument, upon the actual call, 
        arguments will be left-filled for those placeholders.
        
        For example:
        
        >>> _(operator.add).curry(_, 'foo')('bar') == 'barfoo'
        """
        placeholder = wrap
        def merge_args(curried_args, args):
            assert curried_args.count(placeholder) == len(args), \
                'Need the right ammount of arguments for the placeholders'
            
            new_args = list(curried_args)
            if placeholder in curried_args:
                index = 0
                for arg in args:
                    index = new_args.index(placeholder, index)
                    new_args[index] = arg
            return new_args
        
        @functools.wraps(self)
        def wrapper(*actual_args, **actual_kwargs):
            return self(
                *merge_args(curry_args, actual_args),
                **dict(curry_kwargs, **actual_kwargs)
            )
        return wrapper
    
    @wrapped
    def compose(self, outer):
        return lambda *args, **kwargs: outer(self(*args, **kwargs))
    # REFACT consider aliasses wrap = chain = cast = compose

class Iterable(Wrapper):
    """Add iterator methods to any iterable.
    
    Most iterators in python3 return an iterator by default, which is very interesting 
    if you want to build efficient processing pipelines, but not so hot for quick and 
    dirty scripts where you have to wrap the result in a list() or tuple() all the time 
    to actually get at the results (e.g. to print them) or to actually trigger the 
    computation pipeline.
    
    Thus all iterators on this class are by default immediate, i.e. they don't return the 
    iterator but instead consume it immediately and return a tuple. Of course if needed, 
    there is also an i{map,zip,enumerate,...} version for your enjoyment that returns the 
    iterator.
    """
    
    __iter__ = unwrapped(iter)
    
    @wrapped
    def star_call(self, function, *args, **kwargs):
        "Calls function(*self), but allows to prepend args and add kwargs."
        return function(*args, *self, **kwargs)
    
    # This looks like it should be the same as 
    # starcall = wrapped(lambda function, wrapped, *args, **kwargs: function(*wrapped, *args, **kwargs))
    # but it's not. Why?
    
    @wrapped
    def join(self, with_what):
        """"Like str.join, but the other way around. Bohoo!
        
        Also calls str on all elements of the collection before handing 
        it off to str.join as a convenience.
        """
        return with_what.join(map(str, self))
    
    ## Reductors .........................................
    
    len = wrapped(len)
    max = wrapped(max)
    min = wrapped(min)
    sum = wrapped(sum)
    any = wrapped(any)
    all = wrapped(all)
    reduce = wrapped_forward(functools.reduce)
    
    ## Iterators .........................................
    
    imap = wrapped_forward(map)
    map = tupleize(imap)
    
    istar_map = istarmap = wrapped_forward(itertools.starmap)
    star_map = starmap = tupleize(istarmap)
    
    ifilter = wrapped_forward(filter)
    filter = tupleize(ifilter)
    
    ienumerate = wrapped(enumerate)
    enumerate = tupleize(ienumerate)
    
    ireversed = wrapped(reversed)
    reversed = tupleize(ireversed)
    
    isorted = wrapped(sorted)
    sorted = tupleize(isorted)
    
    @wrapped
    def igrouped(self, group_length):
        "s -> (s0,s1,s2,...sn-1), (sn,sn+1,sn+2,...s2n-1), (s2n,s2n+1,s2n+2,...s3n-1), ..."
        return zip(*[iter(self)]*group_length)
    grouped = tupleize(igrouped)
    
    izip = wrapped(zip)
    zip = tupleize(izip)
    
    @wrapped
    def iflatten(self, level=math.inf):
        "Modeled after rubys array.flatten @see http://ruby-doc.org/core-1.9.3/Array.html#method-i-flatten"
        for element in self:
            if level > 0 and isinstance(element, typing.Iterable):
                for subelement in _(element).iflatten(level=level-1):
                    yield subelement
            else:
                yield element
        return
    flatten = tupleize(iflatten)
    
    igroupby = wrapped(itertools.groupby)
    def groupby(self, *args, **kwargs):
        # Need an extra wrapping function to consume the deep iterators in time
        result = []
        for key, values in self.igroupby(*args, **kwargs):
            result.append((key, tuple(values)))
        return wrap(tuple(result))
    
    def tee(self, function):
        "This override tries to retain iterators, as a speedup"
        if hasattr(self.chain, '__next__'): # iterator
            first, second = itertools.tee(self.chain, 2)
            function(wrap(first, previous=self))
            return wrap(second, previous=self)
        else:
            return super().tee(function)

class Mapping(Iterable):
    
    def __getattr__(self, name):
        "Support JavaScript like dict item access via attribute access"
        if name in self.chain:
            return self[name]
        
        return super().__getattr__(self, name)
        
    @wrapped
    def star_call(self, function, *args, **kwargs):
        "Calls function(**self), but allows to add args and set defaults for kwargs."
        return function(*args, **dict(kwargs, **self))

class Set(Iterable): pass

# REFACT consider to inherit from Iterable? It's how Python works...
class Text(Wrapper):
    "Supports most of the regex methods as if they where native str methods"
    
    # Regex Methods ......................................
    
    search = wrapped_forward(re.search)
    match = wrapped_forward(re.match)
    fullmatch = wrapped_forward(re.match)
    split = wrapped_forward(re.split)
    findall = wrapped_forward(re.findall)
    # REFACT consider ifind and find in the spirit of the collection methods?
    finditer = wrapped_forward(re.finditer)
    sub = wrapped_forward(re.sub, self_index=2)
    subn = wrapped_forward(re.subn, self_index=2)

def make_operator(name):
    __op__ = getattr(operator, name)
    @functools.wraps(__op__)
    def wrapper(self, *others):
        return wrap(__op__).curry(wrap, *others)
    return wrapper

class Each(Wrapper):
    
    for name in dir(operator):
        if not name.startswith('__'):
            continue
        locals()[name] = make_operator(name)
    
    @wrapped
    def __getattr__(self, name):
        return operator.attrgetter(name)
    
    @wrapped
    def __getitem__(self, index):
        return operator.itemgetter(index)
    
    @property
    def call(self):
        class MethodCallerConstructor(object):
            
            _method_name = None
            
            def __getattr__(self, method_name):
                self._method_name = method_name
                return self
            
            def __call__(self, *args, **kwargs):
                assert self._method_name is not None, \
                    'Need to access the method to call first! E.g. _.each.call.method_name(arg1, kwarg="arg2")'
                return wrap(operator.methodcaller(self._method_name, *args, **kwargs))
        
        return MethodCallerConstructor()
    
each_marker = object()
wrap.each = Each(each_marker, previous=None, chain=None)


if __name__ == '__main__':
    import sys
    assert len(sys.argv) == 2, \
        "Usage: python -m fluent 'some code that can access fluent functions without having to import them'"
    
    exec(sys.argv[1], dict(wrap=wrap, _=_, lib=lib))
