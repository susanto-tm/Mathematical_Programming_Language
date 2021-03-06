"""
Abstract Syntax Tree

AST class handles visiting nodes and resolving nodes containing multiple recursive
operations. All nodes are encapsulated within one class "AST" and called directly
from the "eval" method. A list of all the nodes is stored in its parameters and
evaluated based on control flow.
"""

DEBUG_MODE = False

symbols = {'global': {}, 'local': {}}  # holds symbols for variables
state = ["global"]  # a stack that holds current variable state and scope
function_state = []  # a stack that holds current scope of functions !!! Only one way recursion works, not backtracking
# stores different states for when a scope is needed
scope_needed = ['IfElseBlock', 'IfStmt', 'ElseStmt', 'ForStmt', 'ReturnStmt', "WhileStmt"]
returning = [False]  # keeps state for when something returns


class Node:
    def __init__(self, action, param):
        self.action = action
        self.param = param

    def __repr__(self):
        return f'{self.__class__.__name__}'

    __str__ = __repr__


class AST:
    def __init__(self, action, param):
        self.action = action
        self.param = param

    def eval(self):
        if self.action == 'eval':
            debug("BEGIN EXECUTION", "Params:", self.param)
            for node in self.param:
                self.visit(node)

    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method)
        return visitor(node)

    def visit_Literal(self, node):
        if isinstance(node.param, list):
            new_list = []
            for elem in node.param:
                new_list.append(self.visit(elem))
            return new_list

        return node.param

    def visit_List(self, node):
        debug("LIST PROCESSING", node, node.action, node.param)
        if node.action == 'get':
            # Accepts in the form of ListID[expr_list] : param = [IDENTIFIER, expr_list]
            # Get the list variable
            arr = self.visit(Variable(action='get', param=Literal(action="IDEN", param=node.param[0])))
            index = []

            for idx in node.param[1]:  # resolve each indices
                index.append(self.visit(idx))
            debug("SLICE INDICES", index)
            for idx in index:
                if isinstance(idx, list):  # list slicing
                    if any(i not in range(0, len(arr)+1) for i in idx):
                        raise IndexError("list slice out of range")
                    arr = arr[idx[0]:idx[1]:idx[2]]
                elif 0 <= idx < len(arr):
                    arr = arr[idx]
                else:
                    raise IndexError("list index out of range")

            return arr

        elif node.action == 'assign':
            # Accepts in the form of ListID[expr_list] = expr : param = [IDENTIFIER, expr_list, expr]
            arr = self.visit(Variable(action='get', param=Literal(action='IDEN', param=node.param[0])))
            index = []

            for idx in node.param[1]:
                index.append(self.visit(idx))

            assignment = self.visit(node.param[2])

            for idx in index[:-1]:
                if idx < 0 or idx > len(arr):
                    raise IndexError("list index out of range")
                else:
                    arr = arr[idx]

            arr[index[-1]] = assignment

        elif node.action == 'slice':
            # Accepts in the form of expr : expr : expr, params = [expr, expr, expr (default 1)]
            # Accepts in the form of ListID[expr : expr : expr] : param = [IDENTIFIER, expr, expr, expr | 1 default]
            # arr = self.visit(Variable(action='get', param=Literal(action='IDEN', param=node.param[0])))
            start = self.visit(node.param[0])
            end = self.visit(node.param[1])
            step = self.visit(node.param[2])

            if any(not isinstance(param, int) for param in [start, end, step]):
                raise TypeError("slice indices must be integers")

            return [start, end, step]

        elif node.action == 'range':
            # Accepts in the form of [INT...INT] or [INT...INT, expr] : param = range
            return self.visit(node.param)  # returns a list of range

    def visit_Print(self, node):
        debug("PRINT", node, node.action, node.param)

        if node.param is None:
            print()
        else:
            print(' '.join(str(self.visit(x)) for x in list(node.param)))

    def visit_Variable(self, node):
        debug("VARIABLE", node, node.action, node.param, symbols)
        if len(function_state) != 0:
            local_symbols = symbols['local'][function_state[0]]
            # end scope search at local, which is on top of function scope
            global_idx = state.index(function_state[0])
        else:
            local_symbols = symbols['local']
            global_idx = -1
        if node.action == 'assign':
            # visit right hand side to see what value it holds
            lhs = node.param[0]
            rhs = self.visit(node.param[1])
            if lhs in symbols['global'] or lhs in [local_symbols[scope] for scope in state[1:global_idx]]:
                raise NameError(f"name '{node.param[0]}' already exist")
            debug("ASSIGNMENT STATE", state)
            if state[0] in local_symbols:
                # local key only exists if it is added in different scopes
                local_symbols[state[0]][lhs] = rhs
            else:
                symbols['global'][lhs] = rhs

            return rhs

        elif node.action == 'reassign' or node.action == 'reassign_get':
            error = True
            lhs = node.param[0]
            rhs = self.visit(node.param[1])
            if lhs in symbols['global']:
                symbols['global'][lhs] = rhs
                error = False

                if node.action == 'reassign_get':
                    return symbols['global'][lhs]

            elif lhs not in symbols['global']:
                if state[0] in local_symbols:
                    var_scope = ""
                    for scope in state[:global_idx]:  # search all local states except last scope: global
                        if lhs in local_symbols[scope]:
                            local_symbols[scope][lhs] = rhs
                            error = False
                            var_scope = scope

                    if node.action == 'reassign_get':
                        return local_symbols[var_scope][lhs]

            if error:
                raise NameError(f"name '{node.param[0]}' not defined")

        elif node.action == 'get':
            identifier = self.visit(node.param)
            if identifier in symbols['global']:
                return symbols['global'][identifier]
            elif identifier not in symbols['global']:
                debug("ARGUMENT", state[:global_idx], symbols['local'], local_symbols, global_idx, state)
                if len(function_state) <= 1:
                    for scope in state[:global_idx]:  # move up a scope and check if variable exists
                        if identifier in local_symbols[scope]:
                            debug("GETTING FROM", scope, identifier)
                            return local_symbols[scope][identifier]
                else:
                    # Get function's parameter from previous function calls
                    # Start at 1 if updating params since recursive calls get updated params from previous calls
                    # Start at 0 if in local space where variables are within current space
                    start_index = 0 if state[0] != 'params' else 1
                    for func in function_state[start_index:]:
                        func_param_from = symbols['local'][func]
                        for local_scope in func_param_from.keys():
                            if identifier in func_param_from[local_scope]:
                                return func_param_from[local_scope][identifier]

            raise NameError(f"name '{identifier}' not defined")

    def visit_BinaryOp(self, node):
        debug("BINARY OP", node, node.action, node.param)
        left = self.visit(node.param[0])
        op = node.param[1]
        right = self.visit(node.param[2])

        result = {
            '+': lambda a, b: a + b,
            '-': lambda a, b: a - b,
            '*': lambda a, b: a * b,
            '/': lambda a, b: a / b,
            '%': lambda a, b: a % b,
            '^': lambda a, b: a ** b,
            '<=': lambda a, b: a <= b,
            '>=': lambda a, b: a >= b,
            '<': lambda a, b: a < b,
            '>': lambda a, b: a > b,
            '==': lambda a, b: a == b,
            '!=': lambda a, b: a != b,
        }[op](left, right)

        return result

    def visit_VariableBinopReassign(self, node):
        debug("VARIABLE BINOP REASSIGN", node, node.action, node.param)
        op = {
            '+=': '+',
            '-=': '-',
            '*=': '*',
            '/=': '/',
            '%=': '%',
            '^=': '^',
        }[node.action]

        result = self.visit(BinaryOp(action='binop', param=[node.param[0], op, node.param[1]]))

        return result

    def visit_VariableIncrDecr(self, node):
        debug("INCREMENT OR DECREMENT", node, node.action, node.param)
        op = {
            '++': '+',
            '--': '-'
        }[node.action]

        result = self.visit(BinaryOp(action='binop', param=[node.param, op, Literal(action='INTCONST', param=1)]))

        return result

    def visit_BoolOp(self, node):
        debug("BOOLOP", node, node.action, node.param)
        params = list(node.param)
        if isinstance(params[0], str) and params[0].upper() == "NOT":
            params.pop(0)
            result = self.visit(params.pop(0))
            if result:  # if result is true, not result is False so cond is false
                result = False
            else:  # if result is false, not result is True so cond is True
                result = not result
        else:
            result = self.visit(params.pop(0))
        if len(params) != 0:
            # if op is AND and the first argument is false return false
            if isinstance(params[0], str) and params[0].upper() == "AND" and result is False:
                return False

            while len(params) >= 2:
                left = result
                op = params.pop(0).upper()
                right = self.visit(params.pop(0))
                result = {
                    "AND": lambda a, b: a and b,
                    "OR": lambda a, b: a or b
                }[op](left, right)

        debug("BOOLOP RETURN", result)

        return result

    def visit_IfElseBlock(self, node):
        # combines both if and else blocks to manage the control flow
        returned = False
        ret, if_branch = self.visit(node.param[0])
        if not if_branch:
            ret, returned = self.visit(node.param[1])

        debug("IF STMT RET", ret)

        if returning[0] and ret is not None:
            returned = True

        return ret, returned

    def visit_IfStmt(self, node):
        local_symbols = self.determine_local()
        # holds evaluation of an if statement and returns if an else will be evaluated
        # node.param[0] holds the condition and node.param[1] holds the basic block
        debug("IF STATEMENT", node, node.action, node.param)
        evaluated, ret, returned = False, None, False
        self.add_scope('if', local_symbols)

        if self.visit(node.param[0]):
            # since operations are basic blocks, they are always in list format
            for actions in node.param[1]:
                if actions.__class__.__name__ in scope_needed:
                    ret, returned = self.visit(actions)
                else:
                    self.visit(actions)

                if returned:
                    debug("RET FROM IF", ret, returned, actions)
                    returning[0] = True
                    break

            evaluated = True  # for if else statements, method will decide whether else is needed

        self.reset_scope(local_symbols)

        return (ret, False) if not evaluated else (ret, True)

    def visit_ElseStmt(self, node):
        local_symbols = self.determine_local()
        debug("ELSE STATEMENT", node, node.action, node.param)
        self.add_scope('else', local_symbols)
        ret, returned = None, False

        if isinstance(node.param, list):
            for actions in node.param:
                if actions.__class__.__name__ in scope_needed:
                    ret, returned = self.visit(actions)
                else:
                    self.visit(actions)

                if returned:
                    returning[0] = True
                    break

        else:
            self.visit(node.param)

        self.reset_scope(local_symbols)

        return ret, returned

    def visit_Range(self, node):
        debug("RANGE", node, node.action, node.param)
        start = self.visit(node.param[0])
        end = self.visit(node.param[1])
        step = self.visit(node.param[2])

        error = ""
        if not isinstance(start, int):
            error = type(start)
        elif not isinstance(end, int):
            error = type(end)
        elif not isinstance(step, int):
            error = type(step)

        if error:
            raise TypeError(f"'{error}' object cannot be interpreted as an integer")

        return list(range(start, end, step))

    def visit_ForStmt(self, node):
        # Accepts param = [iterating symbol, range of iteration, block to execute]
        local_symbols = self.determine_local()
        debug("FOR STATEMENT", node, node.action, node.param)
        loop, ret, returned = True, None, False
        self.add_scope('for_loop', local_symbols)
        loop_range = self.visit(node.param[1])
        iter_symbol = node.param[0]

        if not loop_range:  # empty range(0, 0)
            loop = False
        else:
            local_symbols[state[0]][iter_symbol] = loop_range[0]

        block = node.param[2]

        if loop:
            for i in loop_range:
                debug("LOOP ITER", i, loop_range, symbols)
                local_symbols[state[0]][iter_symbol] = i
                for stmt in block:
                    if stmt.__class__.__name__ in scope_needed:
                        ret, returned = self.visit(stmt)  # each new scope is handled by those that need a new scope
                    else:
                        ret = self.visit(stmt)

                    debug("RET FROM LOOP", ret, stmt, returned, stmt, i)
                    if returned and ret is not None and stmt.__class__.__name__ in scope_needed:
                        debug("LOOP", ret, returned, stmt.action, state[0])
                        returning[0] = True
                        break

                if returned and ret is not None:
                    break

        self.reset_scope(local_symbols)

        # Only reset returned (to fix if statements) if something is returning
        if not returning[0]:
            returned = False

        return ret, returned

    def visit_WhileStmt(self, node):
        # Accepts param = [conditions for while, block to execute]
        local_symbols = self.determine_local()
        debug("WHILE STATEMENT", node, node.action, node.param)
        ret, returned = None, False
        self.add_scope("while_loop", local_symbols)

        while self.visit(node.param[0]):
            for actions in node.param[1]:
                if actions.__class__.__name__ in scope_needed:
                    ret, returned = self.visit(actions)
                else:
                    self.visit(actions)

                if returned and ret is not None:
                    debug("RET IN WHILE", ret, actions)
                    returning[0] = True
                    break

            if returning[0]:
                break

        self.reset_scope(local_symbols)

        if not returning[0]:
            returned = False

        return ret, returned

    def visit_FuncBlock(self, node):
        # Called from FuncCall, params = [IDENTIFIER, exec orders]
        debug("FUNCTION BLOCK EXECUTION", node, node.action, node.param, state)
        state.insert(0, "local")
        debug("FUNCBLOCK", state)
        ret_argument, returned = None, False
        for actions in node.param[1]:
            debug("ACTIONS", actions, actions.param)
            if actions.__class__.__name__ in scope_needed:
                ret_argument, returned = self.visit(actions)
            else:
                ret_argument = self.visit(actions)
            debug("RET ARGUMENT", ret_argument, actions)
            if actions.__class__.__name__ == 'ReturnStmt' or returned:
                returning[0] = True
                debug("RET", ret_argument, returned, actions, "RETURNING", returning[0])
                break

        debug("STATE IN FUNCBLOCK 1", ret_argument)
        self.reset_scope_func_decl()  # only removes local and param since local is just introduced
        state.pop(0)  # removes func_scope

        debug("RETURN STMT", ret_argument)

        if ret_argument is not None:
            debug("STATE IN FUNCBLOCK", state)
            return ret_argument

    def visit_FuncCall(self, node):
        debug("FUNCTION CALL", node, node.action, node.param, function_state)
        if node.action == 'exec':
            # Accepts function execution FuncID(expr_list), param = [IDENTIFIER, expr_list]
            # Search if it is a first call with _0 tail
            func_scope = 'func_' + node.param[0]
            new_func_scope = initial_func = func_scope + "_0"
            if initial_func in function_state:
                # If it is a recursive call
                debug("ADD SAME FUNC", func_scope)
                scope_number = 1
                while new_func_scope in function_state:
                    new_func_scope = func_scope + f"_{scope_number}"
                    scope_number += 1
                debug("ADDING FUNC SCOPE 2", func_scope)
                func_scope = self.add_func_scope(new_func_scope)  # add scope and get key for FuncDecl

                # Add new local instance of function
                symbols['local'][func_scope] = {'params': {}, 'local': {}}

                # Copy symbols from initial parameter to the new recursive function parameter
                if symbols['local'][initial_func]['params'] is not None:
                    for key, val in symbols['local'][initial_func]['params'].items():
                        symbols['local'][func_scope]['params'][key] = val

                # Resolve issues regarding function calls and get necessary scopes
                func = symbols['global'][initial_func]
                func_local = symbols['local'][func_scope]['params']
                update_params = [self.visit(param) for param in node.param[1]] if node.param[1] is not None else []
                debug("UPDATING NEW SCOPE", update_params)
                self.check_positional_arguments(update_params, func_local, node)

            else:
                # Resolve issues regarding function calls and get necessary scopes
                func_scope = self.add_func_scope(new_func_scope)  # add scope and get key for FuncDecl
                func = symbols['global'][func_scope]  # get function object
                func_local = symbols['local'][func_scope]['params']
                update_params = [self.visit(param) for param in node.param[1]] if node.param[1] is not None else []
                self.check_positional_arguments(update_params, func_local, node)

            # update the local parameters in the local function symbols
            for i, key in enumerate(func_local.keys()):
                func_local[key] = update_params[i]

            # change object within global function key and get execution orders if first time calling
            if func.__class__.__name__ == "FuncDecl":
                exec_orders = func.param[2]
                symbols['global'][func_scope] = FuncBlock(action='func_block', param=[func_scope, exec_orders])

            # execute function
            current_scope, func_scope = func_scope, initial_func
            ret_stmt = self.visit(symbols['global'][func_scope])
            debug("RETURNING FROM CALL", ret_stmt)

            symbols['local'].pop(current_scope)

            if returning[0]:
                returning[0] = False

            if ret_stmt is not None:
                debug("CURRENT STATE", state, symbols)
                return ret_stmt

        elif node.action == 'len':
            # Accepts a function call in the form len(expr) : params = [expr]
            expr = self.visit(node.param)
            if isinstance(expr, (int, float)):
                raise TypeError(f"object of type '{type(expr)}' has no len()")
            else:
                return len(expr)
        elif node.action == 'trig':
            import math_functions
            debug("TRIG FUNCTION", node, node.action, node.param)
            math_functions.setup()  # increases performance only when needed
            args = []
            for param in node.param[1]:
                args.append(self.visit(param))

            if node.param[0] in ['asin', 'acos', 'atan']:
                trig_func = math_functions.Math(action='Trig-inv', param=args).exec()
            else:
                trig_func = math_functions.Math(action='Trig-angle', param=args).exec()

            return getattr(trig_func, node.param[0])

        elif node.action == 'integral':
            import math_functions
            debug("INTEGRATION FUNCTION", node, node.action, node.param)
            math_functions.setup()
            args = []
            for param in node.param[1]:
                args.append(self.visit(param))
            debug("INTEGRAL ARGS", args)
            if len(args) > 2:
                # Definite integral
                integral = math_functions.Math(action='def_int', param=args).exec()
            else:
                # Indefinite Integral
                integral = math_functions.Math(action='indef_int', param=args).exec()

            debug("INTEGRAL FUNC SCOPE", symbols, function_state, state)
            # Check if given in a function and get params
            if len(args) <= 2:
                if len(function_state) != 0:
                    if args[1] in symbols['local'][function_state[0]]['params']:
                        return integral.function.subs(
                            args[1], symbols['local'][function_state[0]]['params'][args[1]]).evalf()
                else:
                    return str(integral.function) + ' + C'
            else:
                return integral.function.evalf()

        elif node.action == 'deriv':
            import math_functions
            debug("DIFFERENTIATE", node, node.action, node.param)
            math_functions.setup()
            args = []
            for param in node.param[1]:
                args.append(self.visit(param))

            diff = math_functions.Math(action='deriv', param=args).exec()

            if len(function_state) != 0:
                # Check if derivative in a function
                if args[1] in symbols['local'][function_state[0]]['params']:
                    return diff.function.subs(args[1], symbols['local'][function_state[0]]['params'][args[1]]).evalf()

            else:
                return diff.function

        elif node.action == 'min' or node.action == 'max':
            # Accepts in form max( expr_list ) or min( expr_list ), params = [expr_list]
            debug("MIN MAX FUNCTION", node, node.action, node.param)
            args = []
            for param in node.param:
                new_arg = self.visit(param)
                if isinstance(new_arg, list):
                    args.extend(new_arg)
                else:
                    args.append(new_arg)

            if node.action == 'min':
                return min(*args)
            elif node.action == 'max':
                return max(*args)

        elif node.action == 'typecast':
            # Accepts in form int(expr), float(expr), str(expr), or list(expr), params = [func, expr]
            debug("TYPE CASTING", node, node.action, node.param)
            arg = self.visit(node.param[1])

            if node.param[0].upper() not in ["LIST", "STR"]:
                result = {
                    "INT": lambda a: int(a),
                    "FLOAT": lambda a: float(a),
                }[node.param[0].upper()](arg)

            elif node.param[0].upper() == "STR":
                result = f"'{arg}'"

            else:
                if isinstance(arg, (int, float)):
                    result = list([arg])
                elif isinstance(arg, (list, str)):
                    result = list(arg)
                else:
                    raise TypeError(f"'{type(arg)}' object is not iterable")

            return result

        elif node.action == 'type':
            # Accepts in form type(expr), params = [expr]
            debug("TYPE FUNCTION", node, node.action, node.param)
            return type(self.visit(node.param))

    def visit_FuncDecl(self, node):
        if node.action == 'func_block':
            # Accepts function block, param = [IDENTIFIER, expr_list, execution block]
            debug("FUNCTION DECLARE", node, node.action, node.param)
            # initialize function scope with 0 for very first call
            func_scope = self.add_func_scope('func_' + node.param[0] + "_0")
            symbols['local'][func_scope] = {'params': {}, 'local': {}}

            if node.param[1] is not None:
                for var_param in node.param[1]:
                    debug("VAR_PARAM", var_param.action)
                    self.visit(var_param)

            symbols['global'][func_scope] = node
            debug("UPDATED SYMBOLS", symbols, symbols['global'][func_scope].param)

            self.reset_scope_func_decl()

        elif node.action == 'func_math':
            # Accepts function in the form of ID(input_var, input_var)
            debug("FUNCTION DECLARE", node, node.action, node.param)
            func_scope = self.add_func_scope('func_' + node.param[0] + '_0')
            symbols['local'][func_scope] = {'params': {}, 'local': {}}

            if node.param[1] is None:
                raise TypeError(f"{node.param[0]}() expects at least 1 positional argument")

            # Resolve get Variables and assign instead
            args = node.param[1]
            for arg in args:
                variable = arg.param.param
                self.visit(Variable(action='assign', param=[variable, Literal(action="INTCONST", param=0)]))

            symbols['global'][func_scope] = node
            debug("UPDATED SYMBOLS", symbols)

            self.reset_scope_func_decl()

    def visit_ReturnStmt(self, node):
        # Accepts in the form RETURN expr_list : params = [expr_list] : possible future support for multiple returns
        debug("RETURNING", node, node.action, node.param)

        if node.param is not None:
            ret_args = []
            for args in node.param:
                ret_args.append(self.visit(args))

            if len(ret_args) == 1:
                debug("RETURN STMT FINAL", ret_args[0])
                return ret_args[0], True
        else:
            return None, True

    def visit_SwitchStmt(self, node):
        debug("SWITCH BLOCK", node, node.action, node.param)
        # Switch Statement in the form switch (expr) { case_list }, params = [expr, case_list]
        switch_scope = self.add_scope('switch', symbols['local'])
        cond_expr = self.visit(node.param[0])  # get expression symbol
        # Evaluate each case, if break is hit in one then break the loop
        for case in node.param[1]:
            if case.__class__.__name__ != "DefaultStmt":
                case.param.insert(0, [switch_scope, cond_expr])
            else:
                case.param.insert(0, switch_scope)
            returned = self.visit(case)

            if returned:
                break

        self.reset_scope(symbols['local'])

    def visit_CaseStmt(self, node):
        # Case Statement in the form case expr { basic_block },
        # params = [(switch_scope, cond_expr (SwitchStmt)), expr, basic_block]
        debug("CASE STATEMENT", node, node.action, node.param, symbols)
        switch_scope, cond = node.param[0][0], node.param[0][1]
        has_break = False
        self.add_scope('case', symbols['local'][switch_scope])

        if cond == self.visit(node.param[1]):
            for stmt in node.param[2]:
                ret, returned = self.visit(stmt)

                if ret == 'break':
                    has_break = True
                    break

            if not has_break:
                raise SyntaxError("expected 'break' at the end of a case")

        self.reset_scope(symbols['local'][switch_scope])

        return has_break

    def visit_DefaultStmt(self, node):
        # Default Statement in the form default { basic_block }, params = [switch_scope, basic_block]
        debug("DEFAULT STATEMENT", node, node.action, node.param)
        switch_scope, has_break = node.param[0], False
        self.add_scope('default', symbols['local'][switch_scope])

        for stmt in node.param[1:]:
            ret = self.visit(stmt)

            if ret == 'break':
                has_break = True
                break

        if not has_break:
            raise SyntaxError("expected 'break' at the end of default case")

        self.reset_scope(symbols['local'][switch_scope])

        return has_break

    def visit_BreakStmt(self, node):
        debug("BREAK STATEMENT", node, node.action, node.param)
        if node.param == 'break':
            return node.param

    def check_positional_arguments(self, update_params, func_local, node):
        # Check for the number of positional arguments
        if len(update_params) < len(func_local.keys()):
            raise TypeError(f"{node.param[0]}() missing {len(func_local) - len(update_params)} required "
                            f"positional argument")
        elif len(update_params) > len(func_local.keys()):
            raise TypeError(f"{node.param[0]}() takes {len(func_local.keys())} positional arguments but "
                            f"{len(update_params)} were given")

    def add_scope(self, scope, location):
        scope_number = 0  # the higher the number, the deeper the scope
        new_state = scope + str(scope_number)

        # search for existing scopes and rename until a new name is found
        while new_state in state:
            scope_number += 1
            new_state = scope + str(scope_number)
        state.insert(0, new_state)  # create push a new scope to the stack
        location[new_state] = {}  # create a new scope to store local variables

        return new_state

    def add_func_scope(self, scope):
        debug("INITIAL SCOPE", state)
        state.insert(0, scope)
        state.insert(0, 'params')
        function_state.insert(0, scope)
        debug("ADDING FUNC SCOPE", state)

        return scope

    def determine_local(self):
        if len(function_state) != 0:
            return symbols['local'][function_state[0]]
        else:
            return symbols['local']

    def reset_scope_func_decl(self):
        debug("RESETING FUNC SCOPE", state, function_state)
        state.pop(0)
        state.pop(0)
        function_state.pop(0)

    def reset_scope(self, location):
        debug("RESETING SCOPE", location)
        location.pop(state[0])
        state.pop(0)


"""
-----------------------------------------------------------------------------------
Node Object Definitions

# Organizes AST calls into objects to be visited and evaluated based on Class Name
-----------------------------------------------------------------------------------
"""


class Print(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class Variable(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class VariableBinopReassign(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class VariableIncrDecr(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class Literal(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class BinaryOp(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class BoolOp(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class IfElseBlock(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class IfStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class ElseStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class Range(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class ForStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class WhileStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class List(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class FuncDecl(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class FuncCall(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class FuncBlock(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class ReturnStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class SwitchStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class CaseStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class BreakStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


class DefaultStmt(Node):
    def __init__(self, action, param):
        super().__init__(action, param)


"""
-----------------------------------------------------------------------------------
Debugging Tool
-----------------------------------------------------------------------------------
"""


def debug(*params):
    if DEBUG_MODE:
        print("[DBG] %s" % (' : '.join(str(x) for x in params),))
