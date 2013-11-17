#     Copyright 2013, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Low level variable code generation.

"""

from nuitka import Variables

from .Identifiers import (
    MaybeModuleVariableIdentifier,
    ModuleVariableIdentifier,
    TempObjectIdentifier,
    NameIdentifier
)

from .ConstantCodes import getConstantCode

def _getContextAccess( context, force_closure = False ):
    # Context access is variant depending on if that's a created function or
    # not. For generators, they even share closure variables in the common
    # context.
    if context.isPythonModule():
        return ""
    else:
        function = context.getFunction()

        if function.needsCreation():
            if function.isGenerator():
                if force_closure:
                    return "_python_context->common_context->"
                else:
                    return "_python_context->"
            else:
                if force_closure:
                    return "_python_context->"
                else:
                    return ""
        else:
            if function.isGenerator():
                return "_python_context->"
            else:
                return ""


def getVariableHandle( context, variable ):
    assert isinstance( variable, Variables.Variable ), variable

    var_name = variable.getName()

    if variable.isParameterVariable() or \
       variable.isLocalVariable() or \
       variable.isClassVariable() or \
       ( variable.isClosureReference() and not variable.isTempVariableReference() ):
        from_context = _getContextAccess(
            context       = context,
            force_closure = variable.isClosureReference()
        )

        code = from_context + variable.getCodeName()

        if variable.isParameterVariable():
            hint = "parameter"
        elif variable.isClassVariable():
            hint = "classvar"
        elif variable.isClosureReference():
            hint = "closure"
        else:
            hint = "localvar"

        return NameIdentifier(
            hint      = hint,
            name      = var_name,
            code      = code,
            ref_count = 0
        )
    elif variable.isTempVariableReference() and \
         variable.isClosureReference() and \
         variable.isShared( True ):
        return TempVariableIdentifier(
            var_name     = var_name,
            from_context = _getContextAccess(
                context       = context,
                force_closure = True
            )
        )
    elif variable.isTempVariableReference():
        variable = variable.getReferenced()

        if variable.isTempVariableReference():
            variable = variable.getReferenced()

        if variable.needsLateDeclaration():
            from_context = ""
        else:
            from_context = _getContextAccess(
                context,
                variable.isShared( True )
            )

        if variable.isShared( True ):
            return NameIdentifier(
                hint      = "tempvar",
                name      = var_name,
                code      = from_context + variable.getCodeName(),
                ref_count = 0
            )
        elif not variable.getNeedsFree():
            return TempObjectIdentifier(
                var_name     = var_name,
                code         = from_context + variable.getCodeName()
            )
        else:
            return NameIdentifier(
                hint      = "tempvar",
                name      = var_name,
                code      = from_context + variable.getCodeName(),
                ref_count = 0
            )
    elif variable.isMaybeLocalVariable():
        context.addGlobalVariableNameUsage( var_name )

        assert context.getFunction().hasLocalsDict(), context

        return MaybeModuleVariableIdentifier(
            var_name         = var_name,
            module_code_name = context.getModuleCodeName()
        )
    elif variable.isModuleVariable():
        context.addGlobalVariableNameUsage(
            var_name = var_name
        )

        return ModuleVariableIdentifier(
            var_name         = var_name,
            module_code_name = context.getModuleCodeName()
        )
    else:
        assert False, variable

def getVariableCode( context, variable ):
    var_identifier = getVariableHandle(
        context  = context,
        variable = variable
    )

    return var_identifier.getCode()

def getLocalVariableInitCode( context, variable, init_from = None,
                              in_context = False ):
    # This has many cases to deal with, so there need to be a lot of branches.
    # pylint: disable=R0912

    assert not variable.isModuleVariable()

    assert init_from is None or hasattr( init_from, "getCodeTemporaryRef" )

    result = variable.getDeclarationTypeCode( in_context )

    # For pointer types, we don't have to separate with spaces.
    if not result.endswith( "*" ):
        result += " "

    store_name = variable.getMangledName()

    result += variable.getCodeName()

    if not in_context:
        if variable.isTempVariable():
            assert init_from is None

            if variable.isShared( True ):
                result += "( NULL )"
            elif not variable.getNeedsFree():
                result += " = " + variable.getDeclarationInitValueCode()
        else:
            result += "( "

            result += "%s" % getConstantCode(
                context  = context,
                constant = store_name
            )

            if init_from is not None:
                result += ", %s" % init_from.getCodeExportRef()

            result += " )"

    result += ";"

    return result
