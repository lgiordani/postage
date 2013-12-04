# -*- coding: latin-1 -*-

"""A library to handle microthreads.

.. moduleauthor:: Leonardo Giordani <giordani.leonardo@gmail.com>

"""

class ExitScheduler(ValueError):
    """This exception is used to signal the scheduler it has to quit operations"""
    pass


class MicroThread(object):
    """This is a MicroThread.
    
    This object can be added to a MicroScheduler and executed concurrently with other MicroThreads, in a cooperative
    multitasking environment.
    
    User must implement at least the step() method, which is executed in an infinite loop, yielding the control
    after each execution. Just after the creation of the generator next() is called to run the create() method, which
    can be reimplemented to provide initialization code.
    """
    
    def step(self):
        """Override this to build your microthread.
        This method can run for an indefinite time, blocking all other microthreads"""
        pass

    def create(self):
        """Override this to build your microthread
        This method will be run only once just after the initialization"""
        pass

    def main(self):
        """The main MicroThread loop.
        This calls self.create() and returns a generator, then enters an infinite loop calling self.step()"""
        # Since this is a microthread it returns a generator
        self.create()
        yield 1
        # This is the microthread loop: it just runs the step() method at each call
        while 1:
            self.step()
            yield 1


class MicroScheduler(object):
    """This is a MicroThread scheduler.
    
    MicroThreads can be added to the scheduler and are executed in a cooperative multitasking environment, i.e.
    they can execute without time limits and have to explicitly return control through a yield statement.
    
    If a MicroThread raises StopIteration it will not be rescheduled; so this is the correct way to terminate operations
    in a MicroThread. If it raises ExitScheduler, the scheduler will finish the current scheduled iteration and then exit.
    This is useful to build terminating protocols for the scheduler.
    """
    def __init__(self, autoquit=False):
        self.active_microthreads = []
        self.scheduled_microthreads = []
        self.shutdown = False
        
        #Automatically quit when no more microthreads are running
        self.autoquit = autoquit

    def add_microthread(self, mthread):
        """Adds a MicroThread to the poll of active ones. This method calls main() and next() on the MicroThread,
        thus building the generator and executing the possible create()."""
        g = mthread.main()
        g.next()
        self.active_microthreads.append(g)

    def main(self):
        """The MicroScheduler is itself a MicroThread, so this function returns a generator.
        There is currently no create() for the MicroScheduler.
        This method enters an infinite loop, where the active MicroThreads are continuously rescheduled until
        they raise StopIteration; the scheduler returns the control to the main program after the execution
        of each MicroThread and if the poll of active microthreads is empty.
        """
        
        # Since this is a microthread (see later) it returns a generator
        yield 1

        # This is the main machine loop. Since this is a generator (microthread) itself
        # each exit point is realized through a StopIteration exception
        # This allows the machine itself to be part of a bigger system.
        while 1:
            # If this machine has no processes just skip this sycle
            #print "Scheduled:", len(self.scheduled_microthreads)
            #print "Active:", len(self.active_microthreads)
            if len(self.active_microthreads) == 0:
                yield 1

            # The processes in active queue are run
            for thread in self.active_microthreads:
                #print process
                #print "Now running process", process
                try:
                    thread.next()
                    # Queue the program for the next cycle
                    self.scheduled_microthreads.append(thread)
                except ExitScheduler:
                    self.shutdown = True
                except StopIteration:
                    pass
                
                yield 1
                
            if self.shutdown:
                raise StopIteration
            
            self.active_microthreads = self.scheduled_microthreads
            self.scheduled_microthreads = []
            
            if self.autoquit is True and len(self.active_microthreads) == 0:
                raise StopIteration
