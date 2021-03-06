#!/usr/bin/env python3
# encoding: utf8
# license: ISC (MIT/BSD compatible) https://choosealicense.com/licenses/isc/

# This library is principally created for python 3. However python 2 support may be doable and is welcomed.


"""
To use this module just import it with a short custom name. I recommend:

    >>> import fluentpy as _ # for scripts / projects that don't use gettext
    >>> import fluentpy as _f # for everything else

If you want / need this to be less magical, you can import the main wrapper normally

    >>> from fluentpy import wrap # or `_`, if you're not using gettext

Then to use the module, wrap any value and start chaining off of it. To get started try this:

    $ python3 -m fluentpy '_(_).dir().print()'
    $ python3 -m fluentpy '_(_).help()'

This is incidentally the second way to use this module, as a helper that makes it easier to 
write short fast shell filters in python.

    $ echo "foo\nbar\nbaz" | python3 -m fluentpy "lib.sys.stdin.readlines().map(each.call.upper()).map(print)"

Try to rewrite that in classical python (as a one line shell filter) and see which version spells out what happens in 
which order more clearly.

For further documentation and development see this documentation or the source at https://github.com/dwt/fluent
"""

import functools
import itertools
import math
import operator
import re
import sys
import types
import typing
import pprint

__all__ = ['wrap', '_'] # + @public
__api__ = ['wrap'] # + @protected

NUMBER_OF_NAMED_ARGUMENT_PLACEHOLDERS = 10
# _wrapper_is_sealed = False

# TODO investigate if functools.singledispatch would be a good candidate to replace / enhance this function
def wrap(wrapped, *, previous=None, chain=None):
    """Factory method, wraps anything and returns the appropriate Wrapper subclass.
    
    This is the main entry point into the fluent wonderland. Wrap something and 
    everything you call off of that will stay wrapped in the apropriate wrappers.
    
    It is usually imported like this:
    
        >>> import fluentpy as _
        >>> import fluentpy as _f
        >>> from fluentpy import wrap
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
        chain = previous.self.unwrap
    
    decider = wrapped
    if wrapped is None and chain is not None:
        decider = chain
    
    for clazz, wrapper in by_type:
        if isinstance(decider, clazz):
            return wrapper(wrapped, previous=previous, chain=chain)
    
    return Wrapper(wrapped, previous=previous, chain=chain)

wrap.wrap = wrap._ = _ = wrap
_wrap_alternatives = [wrap]

def public(something, optional_name=None):
    __all__.append(optional_name or something.__name__)
    return protected(something, optional_name=optional_name)

def protected(something, optional_name=None):
    __api__.append(optional_name or something.__name__)
    setattr(wrap, optional_name or something.__name__, something)
    return something

# REFACT consider if this can be achieved with Callable
def wrapped(wrapped_function, additional_result_wrapper=None, self_index=0):
    """
    Using these decorators will take care of unwrapping and rewrapping the target object.
    Thus all following code is written as if the methods live on the wrapped object
    
    Also perfect to adapt free functions as instance methods.
    """
    @functools.wraps(wrapped_function)
    def wrapper(self, *args, **kwargs):
        result = wrapped_function(*args[0:self_index], self.unwrap, *args[self_index:], **kwargs)
        if callable(additional_result_wrapper):
            result = additional_result_wrapper(result)
        return wrap(result, previous=self)
    return wrapper

# REFACT consider if this can be achieved with Callable
def unwrapped(wrapped_function):
    """Like wrapped(), but doesn't wrap the result.
    
    Use this to adapt free functions that should not return a wrapped value"""
    @functools.wraps(wrapped_function)
    def forwarder(self, *args, **kwargs):
        return wrapped_function(self.unwrap, *args, **kwargs)
    return forwarder

# REFACT consider if this can be achieved with Callable
def wrapped_forward(wrapped_function, additional_result_wrapper=None, self_index=1):
    """Forwards a call to a different object
    
    This makes its method available on the wrapper.
    This specifically models the case where the method forwarded to, 
    takes the current object as its first argument.
    
    This also deals nicely with methods that just live on the wrong object.
    """
    return wrapped(wrapped_function, additional_result_wrapper=additional_result_wrapper, self_index=self_index)

# REFACT consider if this can be achieved with Callable
def tupleize(wrapped_function):
    """"Wrap the returned obect in a tuple to force execution of iterators.
    
    Especially usefull to de-iterate methods / function
    """
    @functools.wraps(wrapped_function)
    def wrapper(self, *args, **kwargs):
        return wrap(tuple(wrapped_function(self, *args, **kwargs)), previous=self)
    return wrapper


@protected
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
    
    __slots__ = ['__wrapped', '__previous', '__chain']
    
    def __init__(self, wrapped, *, previous, chain):
        assert wrapped is not None or chain is not None, 'Cannot chain off of None'
        self.__wrapped = wrapped
        self.__previous = previous
        self.__chain = chain # REFACT consider rename to __self?
    
    def __str__(self):
        return "fluentpy.wrap(%s)" % (self.unwrap,)
    
    def __repr__(self):
        return "fluentpy.wrap(%r)" % (self.unwrap,)
    
    # Proxied methods
    
    # for name in dir(operator):
    #     if not name.startswith('__') or name in ('__doc__',):
    #         continue
    #     locals()[name] = wrapped(getattr(operator, name))
    # del name # prevent promotion to class variable
    # Would this make __getitem__ and __getattr__ obsolete?

    __getitem__ = wrapped(operator.getitem)
    __getattr__ = wrapped(getattr)
    # TODO Would be nice if all write acccesses could be given through to the wrapped object. But this breaks many current assumptions of this library. :/
    # Maybe this works if all internal classes define __slots__?
    # def __setattr__(self, name, value):
    #     if not _wrapper_is_sealed:
    #         return super().__setattr__(name, value)
    #     else:
    #         setattr(self.unwrap(), name, value)
    
    # Breakouts
    
    @property
    def unwrap(self):
        """Returns the underlying wrapped value of this wrapper instance."""
        return self.__wrapped
    _ = unwrap # alias
    
    @property
    def previous(self):
        """Returns the previous wrapper in the chain of wrappers.
        
        This allows you to walk the chain of wrappers that where created in your expression. 
        Mainly used internally but might be usefull for introspection.
        """
        return self.__previous
    
    @property
    def self(self):
        "Like .unwrap but handles chaining off of methods / functions that return None like SmallTalk does - and returns a wrapper"
        chain = self.unwrap
        if chain is None:
            chain = self.__chain
        return wrap(chain, previous=self)
    
    @property
    def proxy(self):
        """Allow access to shadowed attriutes.
        
        Breakout that allows access to attributes of the wrapped object that are shadowed by 
        methods on the various wrapper classes.
        
        
            >>> class UnfortunateNames(object):
            >>>     def previous(self, *args):
            >>>         return args
            
        This raises TypeError, because Wrapper.previous() shadows UnfortunateNames.previous():
        
            >>> _(UnfortunateNames()).previous('foo')) 
        
        This works as expected:
        
            >>> _(UnfortunateNames()).proxy.previous('foo')._) == ('foo',)
        
        """
        # @public
        class Proxy(object):
            def __init__(self, proxied):
                self.__proxied = proxied
            def __getattr__(self, name):
                return wrap(getattr(self.__proxied.unwrap, name), previous=self.__proxied)
        return Proxy(self)
    
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
    print = wrapped(print)
    pprint = wrapped(pprint.pprint)
    help = wrapped(help)
    type = unwrapped(type)


# REFACT consider to use wrap as the placeholder to have less symbols? Probably not worth it...
virtual_root_module = "virtual root module"

@protected
class Module(Wrapper):
    """Imports as expressions. Already pre-wrapped.
    
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
        if hasattr(self.unwrap, name):
            return wrap(getattr(self.unwrap, name))
        
        import importlib
        module = None
        if self.unwrap is virtual_root_module:
            module = importlib.import_module(name)
        else:
            module = importlib.import_module('.'.join((self.unwrap.__name__, name)))
        
        return wrap(module)
    
    @wrapped
    def reload(self):
        import importlib
        importlib.reload(self)
        return self
    # TODO add def reload() to reload modules

lib = Module(virtual_root_module, previous=None, chain=None)
lib.__name__ = 'lib'
public(lib)

@protected
class Callable(Wrapper):
    """Higher order methods for callables."""
    
    def __call__(self, *args, **kwargs):
        """"Call through to the wrapped function."""
        def unwrap_if_neccessary(something):
            if isinstance(something, Wrapper):
                return something.unwrap
            return something

        args = list(map(unwrap_if_neccessary, args))
        kwargs = {key: unwrap_if_neccessary(value) for key, value in kwargs.items()}

        result = self.unwrap(*args, **kwargs)
        chain = None if self.previous is None else self.previous
        return wrap(result, previous=self, chain=chain)
    
    @wrapped
    def curry(self, *args_and_placeholders, **default_kwargs):
        """"Like functools.partial, but with a twist.
        
        If you use `wrap` or `_` as a positional argument, upon the actual call, 
        arguments will be left-filled for those placeholders.
        
        >>> _(operator.add).curry(_, 'foo')('bar')._ == 'barfoo'
        
        If you use wrap._$NUMBER (with $NUMBER < 10) you can take full controll 
        over the ordering of the arguments.
        
        >>> _(a_function).curry(_._0, _._0, _.7)
        
        This will repeat the first argument twice, then take the 8th and ignore all in between.
        
        You can also mix numbered with generic placeholders, but since it can be hard to read, 
        I would not advise it.
        
        There is also `_._args` which is the placeholder for the `*args` variable argument list specifier.
        (Note that it is only supported in the last position of the positional argument list.)
        
        >>> _(operator.add).curry(_.args)('foo', 'bar)._ == 'foobar'
        """
        placeholders = tuple(_wrap_alternatives)
        splat_args_placeholder = wrap._args
        reordering_placeholders = tuple(getattr(wrap, '_%i' % index) for index in range(NUMBER_OF_NAMED_ARGUMENT_PLACEHOLDERS))
        all_placeholders = placeholders + (splat_args_placeholder,) + reordering_placeholders
        def merge_args(args_and_placeholders, args):
            def assert_enough_args(required_number):
                assert len(args) > required_number, \
                    'Not enough arguments given to curried function. Need at least %i, got %i: %r' \
                        % (placeholder_index, len(args), args)
            
            def is_placeholder(needle, haystack):
                return any(map(lambda each: each is needle, haystack))
                
            new_arguments = list()
            placeholder_index = -1
            for index, arg_or_placeholder in enumerate(args_and_placeholders):
                if is_placeholder(arg_or_placeholder, all_placeholders):
                    placeholder_index += 1
                if is_placeholder(arg_or_placeholder, placeholders):
                    assert_enough_args(placeholder_index)
                    new_arguments.append(args[placeholder_index])
                elif is_placeholder(arg_or_placeholder, reordering_placeholders):
                    assert_enough_args(arg_or_placeholder.unwrap)
                    new_arguments.append(args[arg_or_placeholder.unwrap])
                elif is_placeholder(arg_or_placeholder, [splat_args_placeholder]):
                    assert index + 1 == len(args_and_placeholders), \
                        'Variable arguments placeholder <_args> needs to be last'
                    new_arguments.extend(args[placeholder_index:])
                else: # real argument
                    new_arguments.append(arg_or_placeholder)
            return new_arguments
        
        # @functools.wraps(self)
        def wrapper(*actual_args, **actual_kwargs):
            return self(
                *merge_args(args_and_placeholders, actual_args),
                **dict(default_kwargs, **actual_kwargs)
            )
        return wrap(wrapper, previous=self)
    
    @wrapped
    def compose(self, outer):
        """Compose two functions.
        >>>  inner_function.compose(outer_function) \
        ...    == lambda *args, **kwargs: outer_function(inner_function(*args, **kwargs))
        """
        return lambda *args, **kwargs: outer(self(*args, **kwargs))
    # REFACT consider aliasses wrap = chain = cast = compose


# REFACT generalize to absent_default_argument
get_default_marker = object()

@protected
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
    
    All iterators return unwrapped elements by design. Fluent is meant to facilitate 
    chaining, not sprad it's wrapper everywhere. This means you will have to rewrap 
    occasionally.
    """
    
    # __iter__ is not wrapped, and implicitly unwraps. If this is unwanted, use one of the explicit iterators
    # This is neccesary becasue otherwise all iterations would implicitly wrap the iterated elements, making it
    # impossible to use this library in a halfway sensible way with explicit wrapping and unwrapping
    __iter__ = unwrapped(iter)
    def iter(self):
        "Ensure `for each in iterable:` works on wrapped elements"
        for element in self.unwrap:
            yield wrap(element, previous=self)
    
    @wrapped
    def star_call(self, function, *args, **kwargs):
        "Calls `function(*self)`, but allows to prepend args and add kwargs."
        return function(*args, *self, **kwargs)
    
    # This looks like it should be the same as 
    # starcall = wrapped(lambda function, wrapped, *args, **kwargs: function(*wrapped, *args, **kwargs))
    # but it's not. Why?
    
    @wrapped
    def get(self, index, default=get_default_marker):
        # Not sure this is the best way to support iterators - but there is no clear way in which we can retain the generator 
        if not isinstance(self, typing.Sized):
            # This is very suboptimal, as it consumes the generator till the asked for index. Still, I don't want this to crash on infinite iterators by just doing tuple(self)
            for i, element in enumerate(self):
                if index == i:
                    return element
            return default
        
        if default is not get_default_marker and index >= len(self):
            return default
        
        return self[index]
        
    @wrapped
    def join(self, with_what):
        """"Like str.join, but the other way around. Bohoo!
        
        Also calls str on all elements of the collection before handing 
        it off to str.join as a convenience.
        """
        return with_what.join(map(str, self))
    
    ## Converters ........................................

    tuplify = wrapped(tuple)
    listify = wrapped(list)
    dictify = wrapped(dict)
    setify = wrapped(set)

    freeze = tuplify
    
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
        """Cut self into tupels of length group_length
        s -> (s0,s1,s2,...sn-1), (sn,sn+1,sn+2,...s2n-1), (s2n,s2n+1,s2n+2,...s3n-1), ..."""
        return zip(*[iter(self)]*group_length)
    grouped = tupleize(igrouped)
    
    izip = wrapped(zip)
    zip = tupleize(izip)
    
    @wrapped
    def iflatten(self, level=math.inf):
        "Modeled after rubys array.flatten @see http://ruby-doc.org/core-1.9.3/Array.html#method-i-flatten"
        for element in self:
            if level > 0 and isinstance(element, typing.Iterable):
                for subelement in wrap(element).iflatten(level=level-1):
                    yield subelement
            else:
                yield element
        return
    flatten = tupleize(iflatten)
    
    igroupby = wrapped(itertools.groupby)
    def groupby(self, *args, **kwargs):
        # Need an extra wrapping function to consume the values iterators before the next iteration invalidates it
        result = []
        for key, values in self.igroupby(*args, **kwargs):
            result.append((key, tuple(values)))
        return wrap(tuple(result), previous=self)
    
    def tee(self, function):
        "This override tries to retain iterators, as a speedup"
        if hasattr(self.unwrap, '__next__'): # iterator
            first, second = itertools.tee(self.unwrap, 2)
            function(wrap(first, previous=self))
            return wrap(second, previous=self)
        else:
            return super().tee(function)
    
    icycle = wrapped_forward(itertools.cycle)
    cycle = tupleize(icycle)
    
    iaccumulate = wrapped_forward(itertools.accumulate)
    accumulate = tupleize(iaccumulate)
    
    idropwhile = wrapped_forward(itertools.dropwhile, self_index=1)
    dropwhile = tupleize(idropwhile)
    
    ifilterfalse = wrapped_forward(itertools.filterfalse, self_index=1)
    filterfalse = tupleize(ifilterfalse)
    
    # TODO make all (applicable?) methods of itertools available here

@protected
class Mapping(Iterable):
    """Index into dicts like objects. As JavaScript can."""
    
    def __getattr__(self, name):
        "Support JavaScript like dict item access via attribute access"
        if name in self.unwrap:
            return self[name]
        
        return super().__getattr__(name)
    
    # REFACT consider rename to splat_call to differentiate that it does something else tha
    # Callable.star_call
    @wrapped
    def star_call(self, function, *args, **kwargs):
        "Calls `function(**self)`, but allows to add args and set defaults for kwargs."
        return function(*args, **dict(kwargs, **self))

@protected
class Set(Iterable):
    """Mostly like Iterable"""

    freeze = wrapped(frozenset)

# REFACT consider to inherit from Iterable? It's how Python works...
@protected
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

def _make_operator(name):
    __op__ = getattr(operator, name)
    @functools.wraps(__op__)
    def wrapper(self, *others):
        # Can't easily use .curry() here, as that would return a wrapped object and I don't want the lambda builder methods to return wrapped objects - yet.
        # return wrap(__op__).curry(_, *others) #.unwrap
        # FIXME the order of the placeholder likely needs to depend on the operator. All the __r*__ operators need it reversed?
        return lambda placeholder: __op__(placeholder, *others)
    return wrapper

class Each(Wrapper):
    """Create functions from expressions.

    Use ``each.foo`` to create attrgetters, ``each['foo']`` to create itemgetters,
    ``each.call.foo()`` to create methodcallers or ``each == 'foo'`` (with pretty much any operator) to create callable operators.
    
    Note: All generated functions never wrap their arguments or return values.
    """
    
    for name in dir(operator):
        if not name.startswith('__') or name == '__doc__':
            continue
        locals()[name] = _make_operator(name)
    del name # prevent promotion to class variable
    
    def __getattr__(self, name):
        # Experimentally using this to allow attribute access for dictionaries just as all other wrapped dicts would allow
        return lambda obj: getattr(_(obj), name).unwrap
        # return operator.attrgetter(name)
    
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
                return operator.methodcaller(self._method_name, *args, **kwargs)
        
        return MethodCallerConstructor()

each_marker = "lambda generator"
each = Each(each_marker, previous=None, chain=None)
each.__name__ = 'each'
public(each)

# add reordering placeholders to wrap to make it easy to reorder arguments in curry
# arbitrary limit, can be increased as neccessary
for index in range(NUMBER_OF_NAMED_ARGUMENT_PLACEHOLDERS):
    public(wrap(index), '_%i' % index)
public(wrap('*'), '_args')

# Make the module executable via `python -m fluentpy "some fluent using python code"`
if __name__ == '__main__':
    assert len(sys.argv) == 2, \
        "Usage: python -m fluentpy 'some code that can access fluent functions without having to import them'"
    
    # __wrapper_is_sealed = True
    exec(sys.argv[1], vars(wrap))
else:
    @functools.wraps(wrap)
    def executable_module(*args, **kwargs): return wrap(*args, **kwargs)
    executable_module.__name__ = __name__ + '.' + wrap.__name__
    executable_module.module = sys.modules[__name__]
    executable_module.__package__ = __package__
    executable_module.__all__ = __all__
    executable_module.__api__ = __api__
    executable_module.__file__ = __file__
    executable_module.__doc__ = __doc__
    _wrap_alternatives.append(executable_module)
    sys.modules[__name__] = executable_module
    # _wrapper_is_sealed = True
