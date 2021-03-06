import functools, io, os, operator, sys

import unittest
from unittest.mock import patch

from pyexpect import expect
import fluentpy as _


class FluentTest(unittest.TestCase): pass

class WrapperTest(FluentTest):
    
    def test_should_not_wrap_a_wrapper_again(self):
        wrapped = _(4)
        expect(type(_(wrapped).unwrap)) == int
    
    def test_should_provide_usefull_str_and_repr_output(self):
        expect(repr(_('foo'))) == "fluentpy.wrap('foo')"
        expect(str(_('foo'))) == "fluentpy.wrap(foo)"
    
    def test_should_wrap_callables(self):
        counter = [0]
        def foo(): counter[0] += 1
        expect(_(foo)).is_instance(_.Wrapper)
        _(foo)()
        expect(counter[0]) == 1
    
    def test_should_wrap_attribute_accesses(self):
        class Foo(): bar = 'baz'
        expect(_(Foo()).bar).is_instance(_.Wrapper)
    
    def test_should_wrap_item_accesses(self):
        expect(_(dict(foo='bar'))['foo']).is_instance(_.Wrapper)
    
    def test_should_error_when_accessing_missing_attribute(self):
        class Foo(): pass
        expect(lambda: _(Foo().missing)).to_raise(AttributeError)
    
    def test_should_explictly_unwrap(self):
        foo = 1
        expect(_(foo).unwrap).is_(foo)
    
    def test_should_wrap_according_to_returned_type(self):
        expect(_('foo')).is_instance(_.Text)
        expect(_([])).is_instance(_.Iterable)
        expect(_(iter([]))).is_instance(_.Iterable)
        expect(_({})).is_instance(_.Mapping)
        expect(_({1})).is_instance(_.Set)
        
        expect(_(lambda: None)).is_instance(_.Callable)
        class CallMe(object):
            def __call__(self): pass
        expect(_(CallMe())).is_instance(_.Callable)
        
        expect(_(object())).is_instance(_.Wrapper)
    
    def test_should_remember_call_chain(self):
        def foo(): return 'bar'
        expect(_(foo)().unwrap) == 'bar'
        expect(_(foo)().previous.unwrap) == foo
    
    def test_hasattr_getattr_setattr_delattr(self):
        expect(_((1,2)).hasattr('len')._).is_false()
        expect(_('foo').getattr('__len__')()._) == 3
        class Attr(object):
            def __init__(self): self.foo = 'bar'
        expect(_(Attr()).setattr('foo', 'baz').self.foo._) == 'baz'
        
        expect(_(Attr()).delattr('foo').unwrap) == None
        expect(_(Attr()).delattr('foo').self.unwrap).isinstance(Attr)
        expect(_(Attr()).delattr('foo').self.vars()._) == {}
    
    def test_isinstance_issubclass(self):
        expect(_('foo').isinstance(str)._) == True
        expect(_('foo').isinstance(int)._) == False
        expect(_(str).issubclass(object)._) == True
        expect(_(str).issubclass(str)._) == True
        expect(_(str).issubclass(int)._) == False
    
    def test_dir_vars(self):
        expect(_(object()).dir()._).contains('__class__', '__init__', '__eq__')
        class Foo(object): pass
        foo = Foo()
        foo.bar = 'baz'
        expect(_(foo).vars()._) == {'bar': 'baz'}
    
    def test_print(self):
        out = io.StringIO()
        _([1,2,3]).print(file=out)
        expect(out.getvalue()) == '[1, 2, 3]\n'
    
    def test_pprint(self):
        out = io.StringIO()
        _([1,2,3]).pprint(stream=out)
        expect(out.getvalue()) == '[1, 2, 3]\n'
    
    def test_str_and_repr_work(self):
        expect(str(_((1,2)))) == 'fluentpy.wrap((1, 2))'
        expect(repr(_((1,2)))) == 'fluentpy.wrap((1, 2))'
    
    def test_simple_forwards(self):
        expect(_(3).type()) == int
        expect(_('3').type()) == str
    
    def test_tee_breakout_a_function_with_side_effects_and_disregard_return_value(self):
        side_effect = {}
        def observer(a_list): side_effect['tee'] = a_list.join('-')._
        expect(_([1,2,3]).tee(observer)._) == [1,2,3]
        expect(side_effect['tee']) == '1-2-3'
        
        def fnording(ignored): return 'fnord'
        expect(_([1,2,3]).tee(fnording)._) == [1,2,3]
    
    def _test_creating_new_attributes_should_create_attribute_on_wrapped_object(self):
        wrapped = _(object())
        wrapped.foo = 'bar'
        expect(wrapped._.foo) == 'bar'

class CallableTest(FluentTest):
    
    def test_call(self):
        expect(_(lambda: 3)()._) == 3
        expect(_(lambda *x: x)(1,2,3)._) == (1,2,3)
        expect(_(lambda x=3: x)()._) == 3
        expect(_(lambda x=3: x)(x=4)._) == 4
        expect(_(lambda x=3: x)(4)._) == 4
    
    def test_call_unwraps_wrapped_arguments(self):
        expect(_(lambda x: repr(x))(_('foo'))._) == "'foo'"
        expect(_(lambda x: repr(x))(x=_('foo'))._) == "'foo'"
    
    def test_curry(self):
        expect(_(lambda x, y: x*y).curry(2, 3)()._) == 6
        expect(_(lambda x=1, y=2: x*y).curry(x=3)()._) == 6
    
    def test_curry_should_support_placeholders_to_curry_later_positional_arguments(self):
        expect(_(operator.add).curry(_, 'foo')('bar')._) == 'barfoo'
        expect(_(lambda x, y, z: x + y + z).curry(_, 'baz', _)('foo', 'bar')._) == 'foobazbar'
    
    def test_curry_should_allow_reordering_arguments(self):
        expect(_(lambda x, y: x + y).curry(_._1, _._0)('foo', 'bar')._) == 'barfoo'
        expect(_(lambda x, y, z: x + y + z).curry(_._1, 'baz', _._0)('foo', 'bar')._) == 'barbazfoo'
    
    def test_curry_should_raise_if_number_of_arguments_missmatch(self):
        expect(lambda: _(lambda x, y: x + y).curry(_, _)('foo')).to_raise(AssertionError, 'Not enough arguments')
        expect(lambda: _(lambda x, y: x + y).curry(_._1)('foo')).to_raise(AssertionError, 'Not enough arguments')
    
    def test_curry_can_handle_variable_argument_lists(self):
        add = _(lambda *args: functools.reduce(operator.add, args))
        expect(add.curry('foo', _._args)('bar', 'baz')._) == 'foobarbaz'
        expect(add.curry(_, _._args)('foo', 'bar', 'baz')._) == 'foobarbaz'
        expect(add.curry(_._1, _._args)('foo', 'bar', 'baz')._) == 'barbarbaz'
        
        # varargs need to be last
        expect(lambda: add.curry(_._args, _)('foo', 'bar')).to_raise(AssertionError, 'Variable arguments placeholder <_args> needs to be last')
    
    def test_curry_can_be_applied_multiple_times(self):
        add = _(lambda *args: functools.reduce(operator.add, args))
        expect(add.curry(_, 'bar', _).curry('foo', _)('baz')._) == 'foobarbaz'
        expect(add.curry(_._1, 'baz', _._0).curry('foo', _)('bar')._) == 'barbazfoo'
    
    # This sounds like a bad idea, for the same reason, why map won't auto wrap it's arguments
    # def test_curry_unwraps_wrapped_arguments(self):
    #     add = _(lambda *args: functools.reduce(operator.add, args))
    #     expect(add.curry(_, _('bar'), _).curry('foo', _)(_('baz'))._) == 'foobarbaz'
    
    def test_compose_cast_wraps_chain(self):
        expect(_(lambda x: x*2).compose(lambda x: x+3)(5)._) == 13
        expect(_(str.strip).compose(str.capitalize)('  fnord  ')._) == 'Fnord'

class IterableTest(FluentTest):
    
    def test_should_call_callable_with_star_splat_of_self(self):
        expect(_([1,2,3]).star_call(lambda x, y, z: z-x-y)._) == 0
    
    def test_join(self):
        expect(_(['1','2','3']).join(' ')._) == '1 2 3'
        expect(_([1,2,3]).join(' ')._) == '1 2 3'
    
    def test_any(self):
        expect(_((True, False)).any()._) == True
        expect(_((False, False)).any()._) == False
    
    def test_all(self):
        expect(_((True, False)).all()._) == False
        expect(_((True, True)).all()._) == True
    
    def test_len(self):
        expect(_((1,2,3)).len()._) == 3
    
    def test_min_max_sum(self):
        expect(_([1,2]).min()._) == 1
        expect(_([1,2]).max()._) == 2
        expect(_((1,2,3)).sum()._) == 6
    
    def test_map(self):
        expect(_([1,2,3]).imap(lambda x: x * x).call(list)._) == [1, 4, 9]
        expect(_([1,2,3]).map(lambda x: x * x)._) == (1, 4, 9)
    
    def test_starmap(self):
        expect(_([(1,2), (3,4)]).istarmap(lambda x, y: x+y).call(list)._) == [3, 7]
        expect(_([(1,2), (3,4)]).starmap(lambda x, y: x+y)._) == (3, 7)
    
    def test_filter(self):
        expect(_([1,2,3]).ifilter(lambda x: x > 1).call(list)._) == [2,3]
        expect(_([1,2,3]).filter(lambda x: x > 1)._) == (2,3)
    
    def test_zip(self):
        expect(_((1,2)).izip((3,4)).call(tuple)._) == ((1, 3), (2, 4))
        expect(_((1,2)).izip((3,4), (5,6)).call(tuple)._) == ((1, 3, 5), (2, 4, 6))
        
        expect(_((1,2)).zip((3,4))._) == ((1, 3), (2, 4))
        expect(_((1,2)).zip((3,4), (5,6))._) == ((1, 3, 5), (2, 4, 6))
    
    def test_reduce(self):
        # no iterator version of reduce as it's not a mapping
        expect(_((1,2)).reduce(operator.add)._) == 3
    
    def test_grouped(self):
        expect(_((1,2,3,4,5,6)).igrouped(2).call(list)._) == [(1,2), (3,4), (5,6)]
        expect(_((1,2,3,4,5,6)).grouped(2)._) == ((1,2), (3,4), (5,6))
        expect(_((1,2,3,4,5)).grouped(2)._) == ((1,2), (3,4))
    
    def test_group_by(self):
        actual = {}
        for key, values in _((1,1,2,2,3,3)).igroupby()._:
            actual[key] = tuple(values)
        
        expect(actual) == {
            1: (1,1),
            2: (2,2),
            3: (3,3)
        }
        
        actual = _((1,1,2,2,3,3)).groupby()._
        
        expect(actual) == (
            (1, (1,1)),
            (2, (2,2)),
            (3, (3,3)),
        )
    
    def test_tee_should_not_break_iterators(self):
        # This should work because the extend as well als the .call(list) 
        # should not exhaust the iterator created by .imap()
        recorder = []
        def record(generator): recorder.extend(generator)
        expect(_([1,2,3]).imap(lambda x: x*x).tee(record).call(list)._) == [1,4,9]
        expect(recorder) == [1,4,9]
    
    def test_enumerate(self):
        expect(_(('foo', 'bar')).ienumerate().call(list)._) == [(0, 'foo'), (1, 'bar')]
        expect(_(('foo', 'bar')).enumerate()._) == ((0, 'foo'), (1, 'bar'))
    
    def test_reversed_sorted(self):
        expect(_([2,1,3]).ireversed().call(list)._) == [3,1,2]
        expect(_([2,1,3]).reversed()._) == (3,1,2)
        expect(_([2,1,3]).isorted().call(list)._) == [1,2,3]
        expect(_([2,1,3]).sorted()._) == (1,2,3)
        expect(_([2,1,3]).isorted(reverse=True).call(list)._) == [3,2,1]
        expect(_([2,1,3]).sorted(reverse=True)._) == (3,2,1)
    
    def test_flatten(self):
        expect(_([(1,2),[3,4],(5, [6,7])]).iflatten().call(list)._) == \
            [1,2,3,4,5,6,7]
        expect(_([(1,2),[3,4],(5, [6,7])]).flatten()._) == \
            (1,2,3,4,5,6,7)
        
        expect(_([(1,2),[3,4],(5, [6,7])]).flatten(level=1)._) == \
            (1,2,3,4,5,[6,7])
    
    def test_star_call(self):
        expect(_([1,2,3]).star_call(str.format, '{} - {} : {}')._) == '1 - 2 : 3'
    
    def test_should_call_callable_with_wrapped_as_first_argument(self):
        expect(_([1,2,3]).call(min)._) == 1
        expect(_([1,2,3]).call(min)._) == 1
        expect(_('foo').call(str.upper)._) == 'FOO'
        expect(_('foo').call(str.upper)._) == 'FOO'
    
    def test_for_in_should_easily_get_wrapped_items(self):
        for element in _([1,2,3]).iter():
            expect(element).isinstance(_.Wrapper)
    
    def test_get_with_default(self):
        expect(_([1]).get(0, 2)._) == 1
        expect(_([]).get(0, 2)._) == 2
        expect(_([1]).get(0)._) == 1
        expect(lambda: _([]).get(0)).to_raise(IndexError)
    
    def test_get_with_default_should_support_iterators(self):
        expect(_(i for i in range(10)).get(0, 'fnord')._) == 0
        expect(_(i for i in range(10)).get(11, 'fnord')._) == 'fnord'

class MappingTest(FluentTest):
    
    def test_should_call_callable_with_double_star_splat_as_keyword_arguments(self):
        def foo(*, foo): return foo
        expect(_(dict(foo='bar')).star_call(foo)._) == 'bar'
        expect(_(dict(foo='baz')).star_call(foo, foo='bar')._) == 'baz'
        expect(_(dict()).star_call(foo, foo='bar')._) == 'bar'
    
    def test_should_support_attribute_access_to_mapping_items(self):
        expect(_(dict(foo='bar')).foo._) == 'bar'
        expect(_(dict(foo='bar')).keys().listify()._) == ['foo']
        expect(lambda: _(dict(foo='bar')).baz).to_raise(AttributeError, "has no attribute 'baz'")

class SetTest(FluentTest):
    
    def test_should_freeze(self):
        frozen = _({'foo', 'bar', 'baz'}).freeze()._
        expect(frozen).contains('foo', 'bar', 'baz')
        expect(frozen).isinstance(frozenset)

class StrTest(FluentTest):
    
    def test_search(self):
        expect(_('foo bar baz').search(r'b.r').span()._) == (4,7)
    
    def test_match_fullmatch(self):
        expect(_('foo bar').match(r'foo\s').span()._) == (0, 4)
        expect(_('foo bar').fullmatch(r'foo\sbar').span()._) == (0, 7)
    
    def test_split(self):
        expect(_('foo\nbar\nbaz').split(r'\n')._) == ['foo', 'bar', 'baz']
        expect(_('foo\nbar/baz').split(r'[\n/]')._) == ['foo', 'bar', 'baz']
    
    def test_findall_finditer(self):
        expect(_("bazfoobar").findall('ba[rz]')._) == ['baz', 'bar']
        expect(_("bazfoobar").finditer('ba[rz]').map(_.each.call.span())._) == ((0,3), (6,9))
    
    def test_sub_subn(self):
        expect(_('bazfoobar').sub(r'ba.', 'foo')._) == 'foofoofoo'
        expect(_('bazfoobar').sub(r'ba.', 'foo', 1)._) == 'foofoobar'
        expect(_('bazfoobar').sub(r'ba.', 'foo', count=1)._) == 'foofoobar'

class ImporterTest(FluentTest):
    
    def test_import_top_level_module(self):
        expect(_.lib.sys._) == sys
    
    def test_import_symbol_from_top_level_module(self):
        expect(_.lib.sys.stdin._) == sys.stdin
    
    def test_import_submodule_that_is_also_a_symbol_in_the_parent_module(self):
        expect(_.lib.os.name._) == os.name
        expect(_.lib.os.path.join._) == os.path.join
    
    def test_import_submodule_that_is_not_a_symbol_in_the_parent_module(self):
        import dbm
        expect(lambda: dbm.dumb).to_raise(AttributeError)
        
        def delayed_import():
            import dbm.dumb
            return dbm.dumb
        expect(_.lib.dbm.dumb._) == delayed_import()
    
    def test_imported_objects_are_pre_wrapped(self):
        _.lib.os.path.join('/foo', 'bar', 'baz').findall(r'/(\w*)')._ == ['foo', 'bar', 'baz']

    def test_should_allow_reloading_modules(self):
        sensed = {}
        def sensor(*args, **kwargs):
            sensed['args'] = args
            sensed['kwargs'] = kwargs
        
        with patch('importlib.reload', sensor):
            _.lib.os.path.reload()
            expect(sensed['args']) == (_.lib.os.path._, )

class EachTest(FluentTest):
    
    def test_should_produce_attrgetter_on_attribute_access(self):
        class Foo(object):
            bar = 'baz'
        expect(_([Foo(), Foo()]).map(_.each.bar)._) == ('baz', 'baz')
    
    def test_should_produce_itemgetter_on_item_access(self):
        expect(_([['foo'], ['bar']]).map(_.each[0])._) == ('foo', 'bar')
    
    def test_should_produce_callable_on_binary_operator(self):
        expect(_(['foo', 'bar']).map(_.each == 'foo')._) == (True, False)
        expect(_([3, 5]).map(_.each + 3)._) == (6, 8)
        expect(_([3, 5]).map(_.each < 4)._) == (True, False)
    
    def test_should_produce_callable_on_unary_operator(self):
        expect(_([3, 5]).map(- _.each)._) == (-3, -5)
        expect(_([3, 5]).map(~ _.each)._) == (-4, -6)
    
    def test_should_produce_methodcaller_on_call_attribute(self):
        # problem: _.each.call is now not an attrgetter
        # _.each.method.call('foo') # like a method chaining
        # _.each_call.method('foo')
        # _.eachcall.method('foo')
        class Tested(object):
            def method(self, arg): return 'method+'+arg
        expect(_(Tested()).call(_.each.call.method('argument'))._) == 'method+argument'
        expect(lambda: _.each.call('argument')).to_raise(AssertionError, '_.each.call.method_name')
    
    def test_should_behave_as_if_each_was_wrapped(self):
        expect(_.each.first(dict(first='foo'))) == 'foo'
        expect(_([dict(first='foo')]).map(_.each.first)._) == ('foo',)
        
    
    def _test_should_allow_creating_callables_without_call(self):
        # This is likely not possible to attain due to the shortcomming that .foo already
        # needs to create the attgetter, and we cannot distinguish a call to it from the calls map, etc. do
        expect(_.each.foo) == attrgetter('foo')
        expect(_.each.foo(_, 'bar', 'baz')) == methodcaller('foo').curry(_, 'bar', 'baz')
        expect(_.call.foo('bar', 'baz')) == methodcaller('foo').curry(_, 'bar', 'baz')

class WrapperLeakTest(FluentTest):
    
    def test_wrapped_objects_will_wrap_every_action_to_them(self):
        expect(_('foo').upper()).is_instance(_.Wrapper)
        expect(_([1,2,3])[1]).is_instance(_.Wrapper)
        expect(_(lambda: 'foo')()).is_instance(_.Wrapper)
        expect(_(dict(foo='bar')).foo).is_instance(_.Wrapper)
    
    def test_function_expressions_return_unwrapped_objects(self):
        class Foo(object):
            bar = 'baz'
        expect(_.each.bar(Foo())).is_('baz')
        expect((_.each + 3)(4)).is_(7)
        expect(_.each['foo'](dict(foo='bar'))).is_('bar')

class AccessShadowedAttributesOnWrappedObjects(FluentTest):
    
    def test_use_getitem_to_bypass_overrides(self):
        class UnfortunateNames(object):
            def previous(self, *args):
                return args
        
        def producer(*args):
            return UnfortunateNames()
        
        expect(_(producer)().previous('foo')).is_instance(_.Wrapper)
        expect(_(UnfortunateNames()).proxy.previous('foo')._) == ('foo',)
    
    def test_chain_is_not_broken_by_proxy_usage(self):
        class UnfortunateNames(object):
            def previous(self, *args):
                return args
        
        expect(_(UnfortunateNames()).proxy.previous('foo').previous.previous._).is_instance(UnfortunateNames)
    
    def test_smalltalk_like_behaviour_is_not_broken_by_proxy(self):
        class UnfortunateNames(object):
            def previous(self, *args):
                self.args = args
        
        expect(_(UnfortunateNames()).proxy.previous('foo').self.args._) == ('foo',)

class SmallTalkLikeBehaviour(FluentTest):
    
    def test_should_ease_chaining_off_methods_that_return_none(self):
        expect(_([3,2,1]).sort().unwrap) == None
        expect(_([3,2,1]).sort()._) == None
        expect(_([3,2,1]).sort().previous.previous._) == [1,2,3]
        expect(_([3,2,1]).sort().self.unwrap) == [1,2,3]
        
        expect(_([2,3,1]).sort().self.sort(reverse=True)._) == None
        expect(_([2,3,1]).sort().self.sort(reverse=True).previous.previous._) == [3,2,1] # sorted, because in place
        expect(_([2,3,1]).sort().self.sort(reverse=True).self._) == [3,2,1]
        
        class Attr(object):
            foo = 'bar'
        expect(_(Attr()).setattr('foo', 'baz').self.foo._) == 'baz'

class IntegrationTest(FluentTest):
    
    def test_extrac_and_decode_URIs(self):
        from xml.sax.saxutils import unescape
        line = '''<td><img src='/sitefiles/star_5.png' height='15' width='75' alt=''></td>
            <td><input style='width:200px; outline:none; border-style:solid; border-width:1px; border-color:#ccc;' type='text' id='ydxerpxkpcfqjaybcssw' readonly='readonly' onClick="select_text('ydxerpxkpcfqjaybcssw');" value='http://list.iblocklist.com/?list=ydxerpxkpcfqjaybcssw&amp;fileformat=p2p&amp;archiveformat=gz'></td>'''
        
        actual = _(line).findall(r'value=\'(.*)\'').map(unescape)._
        expect(actual) == ('http://list.iblocklist.com/?list=ydxerpxkpcfqjaybcssw&fileformat=p2p&archiveformat=gz',)
    
    def test_call_module_from_shell(self):
        from subprocess import check_output
        output = check_output(
            ['python', '-m', 'fluentpy', "lib.sys.stdin.read().split('\\n').imap(each.call.upper()).map(print)"],
            input=b'foo\nbar\nbaz')
        expect(output) == b'FOO\nBAR\nBAZ\n'
    
    def test_can_import_public_symbols(self):
        from fluentpy import lib,  each, _ as _f, Wrapper
        expect(lib.sys._) == sys
        expect(_f(3)).is_instance(Wrapper)
        expect((each + 3)(4)) == 7
    
    def test_can_get_symbols_via_star_import(self):
        nested_locals = {}
        exec('from fluentpy import *; locals()', {}, nested_locals)
        # need _._ here so we don't get the executable module wrapper that we get from `import fluentpy as _`
        expect(nested_locals).has_subdict( _=_._, wrap=_._, lib=_.lib, each=_.each, _1=_._1, _9=_._9)
        # only symbols from __all__ get imported
        expect(nested_locals.keys()).not_contains('Wrapper')
    
    def test_can_access_original_module(self):
        import types
        expect(_.module).instanceof(types.ModuleType)

class DocumentationTest(FluentTest):
    
    def test_wrap_has_usefull_docstring(self):
        expect(_.__doc__).matches(r'_\(_\)\.dir\(\)\.print\(\)')
        expect(_.__doc__).matches(r'https://github.com/dwt/fluent')
    
    def test_classes_have_usefull_docstrings(self):
        expect(_.Wrapper.__doc__).matches(r'Universal wrapper')
        expect(_.Callable.__doc__).matches(r'Higher order')
        expect(_.Iterable.__doc__).matches(r'Add iterator methods to any iterable')
        expect(_.Mapping.__doc__).matches(r'Index into dicts')
        expect(_.Text.__doc__).matches(r'regex methods')
        
        expect(_.Set.__doc__).matches(r'Mostly like Iterable')
    
    def test_special_proxies_have_usefull_docstrings(self):
        expect(_.lib.__doc__).matches('Imports as expressions')
        expect(_.each.__doc__).matches('functions from expressions')
    
    def test_help_method_outputs_correct_docstrings(self):
        with patch.object(sys, 'stdout', io.StringIO()):
            sys.stdout = io.StringIO()
            help(_)
            expect(sys.stdout.getvalue()).matches('Help on function fluentpy.wrap')
        
        with patch.object(sys, 'stdout', io.StringIO()):
            sys.stdout = io.StringIO()
            _(list).help()
            expect(sys.stdout.getvalue()).matches('Help on class list in module builtins')
    
    def test_lib_and_wrap_have_usefull_repr(self):
        expect(repr(_.lib)).matches('virtual root module')
        expect(repr(_.each)).matches('lambda generator')

