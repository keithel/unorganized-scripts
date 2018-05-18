#include <time.h>
#include <iostream>
#include <string.h>

using std::cout;
using std::endl;

#define STRBUFLEN 1024

static char STRBUFFER[STRBUFLEN];

timespec getTime()
{
    timespec time;
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &time);
    return time;
}

timespec diff(const timespec& start, const timespec& end)
{
    timespec ret;
    if ((end.tv_nsec - start.tv_nsec) < 0)
    {
        ret.tv_sec = end.tv_sec-start.tv_sec-1;
        ret.tv_nsec = 1000000000+end.tv_nsec-start.tv_nsec;
    }
    else
    {
        ret.tv_sec = end.tv_sec-start.tv_sec;
        ret.tv_nsec = end.tv_nsec-start.tv_nsec;
    }
    return ret;
}

void inefficientStringConcat()
{
    for (int j = 0; j < 10000; j++)
    {
    STRBUFFER[0] = '\0';
    for (int i = 0; i < STRBUFLEN/8; i++)
    {
        strncat( STRBUFFER, "Jo", STRBUFLEN);
        strncat( STRBUFFER, "Pa", STRBUFLEN);
        strncat( STRBUFFER, "Ge", STRBUFLEN);
        strncat( STRBUFFER, "Ri", STRBUFLEN);
    }
    }
}

void efficientStringConcat()
{
    for (int j = 0; j < 10000; j++)
    {
    STRBUFFER[0] = '\0';
    for (int i = 0; i < STRBUFLEN; i=i+8)
    {
        strncat( STRBUFFER+i, "Jo", STRBUFLEN-i);
        strncat( STRBUFFER+i+2, "Pa", STRBUFLEN-i);
        strncat( STRBUFFER+i+4, "Ge", STRBUFLEN-i);
        strncat( STRBUFFER+i+6, "Ri", STRBUFLEN-i);
    }
    }
}

timespec timeOperation(timespec& start, timespec& end, void (*function)())
{
    start = getTime();
    // Do stuff
    function();
    end = getTime();
    return diff(start, end);
}

std::ostream& operator<<(std::ostream& os, const timespec& timeSpec)
{
    long timeSpecMS = timeSpec.tv_nsec/1000000;
    os << timeSpec.tv_sec << "s " << timeSpecMS  << "ms "
         << timeSpec.tv_nsec - timeSpecMS*1000000 << "ns";
    return os;
}

int main(int argc, char** argv)
{
    int trials = 1;
    if (argc > 1)
    {
        if (argc 
    }

    timespec end;
    timespec start;
    timespec timeSpent = timeOperation(start, end, inefficientStringConcat);
    cout << timeSpent << endl;

    timeSpent = timeOperation(start, end, efficientStringConcat);
    cout << timeSpent << endl;

    //long timeSpentMS = timeSpent.tv_nsec/1000000;
    //cout << timeSpent.tv_sec << "s " << timeSpentMS  << "ms "
    //     << timeSpent.tv_nsec - timeSpentMS*1000000 << "ns" << endl;

    return 0;
}
