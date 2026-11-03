好了，我们开始讲集合论。集合论是数理逻辑和数学思维的基础，是一个比较基础的东西。

我们直接来看。现在用的是 Thomas 的一本比较流行的教材，作者名字怎么读我还不确定，但不管了。直接看第一章，标题是 Sets，也就是“集合”；Introduction to Sets，就是集合的介绍、导论。

这本书的核心概念就是集合。一个集合，至少在表面上看起来极为简单。

A set is any collection, group or conglomerate。一个集合就是任何 collection、group 或 conglomerate，中文通常翻译成“集合”，也就是把一堆东西集中起来。conglomerate 是一堆东西，或者说一群、一团；当然，群论是另一回事，英文是不是 group theory，我记不得了。反正一系列的东西、集团的东西、一团东西，都可以说是一个集合。

比如，1998年2月纽约城市大学所有注册学生的集合。February 就是二月，我居然还要想一下，简直没文化到这种程度了。还可以有所有自然数中的偶数组成的集合，even 就是偶数。

再比如，在平面 π 上，离给定点 p 恰好两英寸的所有点组成的集合。plane 应该就是“平面”的意思；我不是数学系的，但这点还是知道。inch 虽然念作 inch，意思却是英寸，顺便还能学点英语。还可以有所有粉色大象的集合。有人会问：房间里的粉色大象不是只有一头吗？

Sets are not objects of the real world。集合不是现实世界中的对象，不是像桌子或星星那样真实存在的东西；它们是由我们的心智创造出来的，是头脑想出来的，而不是用手创造出来的。因此，一堆土豆并不是一个“土豆集合”；一滴水里所有水分子组成的集合，也不是作为对象的那滴水本身。集合是头脑设想出来的东西。

人类的心智获得了一种能力：把许多不同的对象，a variety of different objects，看作被某个共同特点束缚在一起、捆绑在一起；通过某一个共同特点，把许多不同的东西放到一起设想。也就是抽象出它们的共同点，然后说这些东西属于同一个整体，至少把它们当作一个集合来把握，从而形成一个由具有这些共同点、这些属性的对象组成的集合。人类具有这种观念的能力：通过事物的共同点把它抽象出来，再统一地、统摄地把握。

那么这里所谓的共同属性，可能 nothing more than the ability to think of these objects together：可能根本没有真正的共同属性，只不过是我把它们放在一起考虑，把它们当成一组东西。比如随便找几个东西，它们其实没有共同点，但我把它们一起思考，这本身就成了它们的“共同点”。于是这些东西就构成一个集合。

因此可以存在一个集合，恰好由 2、7、10、23、29、34 和 11000 组成。尽管很难看出这些数到底有什么共同点，也很难看出到底是什么把它们捆在一起；其实是我把它们捆在一起，把它们作为一个整体来把握。除了我把这些数在头脑中集中到一起之外，它们之间没有什么共同点，也没有什么共同的属性。

接下来是康托。他是德国、或者说日耳曼的数学家，用一系列论文——不是几张纸——在19世纪最后三十年建立起了集合论。

康托这样表达，德文我就不念了；下面有翻译：A set is a collection into a whole of definite distinct objects of our intuition or our thought。一个集合，就是把我们的直观或思想中确定的、彼此不同的对象汇集成一个整体。collection 在这里也翻译成“集合”，a set 就是集合。

也就是说，这个集合由我们的直观对象或思想对象构成；它们是 definite，即清楚明白的；也是 distinct，即彼此可以区分、不会混淆的。我们的直观对象和思维对象形成一个整体，这个整体就是一个 set，也就是集合。

这些对象被称为这个集合的要素，或者说集合里面的成员。The objects from which a given set is composed are called elements：组成一个给定集合的那些对象，就叫这个集合的要素。We also say that they belong to that set，我们也说这些对象或要素属于这个集合。

这些要素属于该集合。In this book we want to develop the theory of sets as a foundation for other mathematical theories。在这本书里，我们要发展集合论，把它作为其他数学理论、数学学科的基础。因此，我们在这里并不关心人的集合，也不关心由分子组成的集合；我讲的不是人类学、社会学，也不是物理学、化学，而只是讨论数学对象的集合，比如数、空间中的点、函数，甚至集合本身组成的集合。事实上，前面三类概念——数、空间点、函数——都可以在集合论里被定义为具有特殊性质的集合；简单说，数学对象和数学概念都可以被定义成集合。我们会在后面几章做这件事。So the only objects with which we are concerned from now on are sets。所以从现在开始，我们唯一关心的对象就是集合。For purposes of illustration，为了说明方便，我们会在数和点被精确定义之前就谈论数集或点集。

为了说明方便，我们会在数和点被清楚定义之前，就讨论数集或点集；也就是说，还没定义清楚什么是数、什么是点，就已经开始用数集和点集了。不过，这样做只会在例子、习题和问题里出现，而不会在理论的主体部分这样做，因为那样是“赖皮”、是违规的：你还没有定义清楚什么是点、什么是数，就已经在说数集和点集了。你不是说数和点本身可以定义成集合吗？那为什么不先把数和点定义成集合，再讨论数集和点集？他说这里有一个先后次序的问题。

由数学对象组成的集合，他举了几个例子。一个例子是由 324 的所有素因子，也就是质因数组成的集合；比如 2、3 等。prime 在这里翻译成素数因子、质因数。还有一个例子是 the set of all numbers divisible by……，也就是所有能被某个数整除的数组成的集合。

接下来是能被零整除的所有数，也就是 divisible by zero 的所有数。但这个集合是空集，因为没有任何数能被零整除，明白吗？

接下来是 the set of all continuous real valued functions on the interval zero to one，也就是从零到一这个区间上所有连续实值函数组成的集合。它指的是这个区间里有定义的所有 real valued 实函数，也就是有值域的实函数，反正就是这一类。

在这个区间里有定义的所有函数，等等。接下来是 the set of all ellipses with major axis five，也就是所有长轴为五的椭圆组成的集合。major axis 就是椭圆的主轴；椭圆有两条轴，这里主轴长是五。我反正不是学数学的，当时学过数学；这个 major axis 查一下就知道，其实几秒钟的事情。

eccentricity 是离心率，这里是三。离心率是椭圆的什么比什么，我记不得了；椭圆的离心率是动点到焦点的距离与动点到准线的距离之比。多少年没学椭圆了，记不得了，不好意思。

第五个例子是 set of all sets whose elements are natural numbers less than twenty，也就是由所有这样的集合组成的集合：这些集合的元素都是小于二十的自然数。只要一个集合的元素是小于二十的自然数，它就属于这个大的集合。对这类例子以及其他许多类似例子的考察表明，sets with which mathematicians work are relatively simple：数学家所处理的集合是相对简单的。

这些例子和其他类似例子表明，数学家所处理的集合是相对简单的。它们包括自然数集及其各种子集，比如所有素数组成的集合，以及 pairs、triples，也就是二元组、三元组，直到一般的 n\-tuples（n 元有序组）的集合。n\-tuples 就是 n 元有序组；这里说的一般 n 元数组应该也是有序组。整数和有理数可以只用这类集合来定义：integers and rational numbers can be defined using only such sets。实数则可以定义为有理数的集合或序列：real numbers can then be defined as sets or sequences of rational numbers。数学分析处理实数集和实函数集，也就是关于实数的函数组成的集合，sets of ordered pairs of real numbers 是有序实数对组成的集合；在一些研究中还会考虑函数集合，甚至函数集合的集合。但一个真正工作的数学家很少会遇到比函数集合的集合更复杂、更高阶的对象。Perhaps it is not surprising that uncritical usage of sets remote from everyday experience may lead to contradiction：不加批判地使用远离日常经验的集合概念，可能会导致矛盾。

数学家一天到晚研究的东西其实都可以用集合来研究，但如果不把集合这个概念弄清楚、用法不加批判，就可能导致矛盾。Consider for example the set R of all those sets which are not elements of themselves：考虑所有不属于自身的集合组成的集合 R。这个 R 是一个由许多集合组成的大集合，里面有很多小集合。也就是说，R 由一切不是自己元素的集合组成；哪些集合会属于 R 呢？只要一个集合不是它自己的元素，它就属于 R。换句话说，R is a set of all sets X such that X doesn't belong to X。

belongs to 读作“属于”，does not belong to 读作“不属于”；这个符号表示属于，那个符号表示不属于。

现在问：R 是否属于 R？这里一自指涉就会出现矛盾。Let us now ask whether R belongs to R。如果 R 属于 R，那么 R is not an element of itself，也就是 R 不是它自己的元素；可 R 的定义要求它的元素都不是自身元素，所以这不符合定义。因为 R 里没有任何元素属于自身，所以 R 不属于 R。Therefore necessarily R does not belong to R。但如果 R 不属于 R，那么 R 就是一个不属于自身的集合；而所有这样的集合都属于 R，于是 R 又属于 R。We conclude that R 属于 R，again a contradiction。这个矛盾就是自指涉的矛盾。其实辩证法里一直会遇到这种结构，黑格尔辩证法里也一直会这样遭遇。

所以集合论从一开始就和辩证法的逻辑不一样，辩证法逻辑学已经不一样了，you understand？因为集合论背后预设了一个数学体系，或者预设了一个直观框架。The argument can be briefly summarized as follows：这个论证可以简要概括如下。定义 R：x 属于 R，当且仅当 x 不属于 x（if and only if x doesn't belong to x）。

现在考虑 x = R。By definition of R，也就是假设 R = x，把两层拍平，直接用 R 代入定义：R 属于 R，当且仅当 R 不属于 R；这就是矛盾。下面是一些评论（A few comments）。关于这个论题有许多讨论，比如罗素的说法，might be helpful，可能有点用，其实没什么用。首先，there is nothing wrong with R being a set of sets：R 是一个由集合组成的集合，这本身没有问题。Many sets whose elements are again sets are legitimately employed in mathematics：在数学中，许多集合的元素本身又是集合，这是正当的用法，可以这么搞。比如 1\.1 中的例子，其实 1\.1 里每个例子都是如此，因为数学概念本身的定义里就是集合；并且一个集合是集合的集合，并不会导致矛盾。Second, it is easy to give examples of elements of R：其次，很容易给出 R 的元素的例子。比如，如果 x 是所有自然数组成的集合，也就是自然数集，那么 x does not belong to x；因为 the set of all natural numbers is not a natural number，自然数集本身不是自然数，它是由自然数组成的集合，并不是自然数。

数学概念本身在定义里就是集合，and do not lead to a contradiction，并且说一个集合会是集合的集合，这并不会导致矛盾。其次，很容易给出 R 的要素的例子。举个例子，如果 x 是所有自然数的集合，也就是自然数集，then x doesn't belong to x，这很正常吧。The set of all natural numbers is not a natural number，自然数集本身不是自然数；它是个集合，对不对？它不是自然数，而是由自然数组成的集合，并不是自然数。And so x belongs to R。但要看你怎么构造这个自然数集，你知道吗？怎么构造自然数定义的？

自然数在标准集合论模型里面，就被定义成一个层层套套的集合，层层套套，它有多少层空集和……我不知道你们说的零，就是他妈的空集的集合，一个集合里面的要素是空集，是这样的吗？哦对，然后那个一是这个……一就是一个层层套套的括号，懂吗？层层套套，就是把零再并上一个空集，然后再套一个集合；零并上一个空集，再套上一个集合。也就是说，这个集合里面有零和一个空集，它这俩。然后二的话，就变成这个集合里面有一，再加上零，再加上一个空集的一个集合。那么这样搞的话，你很难说这是一种构造方式。你按照这种构造方式，你很难说所有自然数构成的集合——因为，懂吗？集合论里面就是说它是重复出现的，就是 you understand。看他怎么定义。他反正这里说了，那很明显，我们头脑里面会认为所有自然数组成的一个集合，它并不是一个自然数，所以自然数集并不属于自然数集本身，对不对？

所以 x 属于 R，这个也没问题，第二步构造也没问题。那么第三步呢？It is not so easy to give examples of sets which do not belong to R。这个却很不容易给出一些例子，这些例子不属于 R。But this is irrelevant，不过这不相干。R 不是说了吗？如果 x 本身不是它自己的要素，那 x 就属于 R；但你很难设想一个 x 是它自己的要素。这好像是无关紧要的。这个定义最可疑的就是第三点，对不对？整个关于 R 的定义最可疑的就是第三点：你怎么去设想一个集合他妈的它是它自己的要素？你找一个集合告诉我它是它自己的要素？啊对，可能就只有人的主体性，对不对？从哲学概念说，这毕竟有自指性，self\-referred，self\-contained，自己包括自己。只有人的主体性是这样的，或者某种智性官能、某种模式，它可以回到它自身，并且把自己囊摄在内去统摄它自身。This is irrelevant。数学家想着：操你妈，哲学问题这么复杂，老子不想了。所以这第三点，我虽然找不到有哪个集合不属于这个 R。

或者说，有哪个集合自己就是自己的要素——但是这不管了，对不对？The foregoing argument，进一步说，这个问题 will result in a contradiction，even if there were no sets which are elements of themselves。之前的论断、之前那个自相矛盾的论断，会导致一个矛盾；尽管不存在一些集合，它们是它们自己的要素，但是之前那个它还是会产生矛盾。A plausible candidate for a set which is an element of itself would be the set of all sets。一个非常 plausible 的、大家比较公认的、比较容易提出来的、比较容易设想的候选——翻译成“看似合理”或“看似可信”的——一个看似可信的、自己是自己要素的集合，就是所有集合的集合，对不对？

由所有集合组成的这个集合，万集之集，是不是？万集之集，包括它自己也是自己的要素嘛？它说，我包括所有的集合，我是一个集合，包括所有的集合，那这里面所有的集合，这个 all 本身就带有自指涉性，对不对？因为它自己要算在内嘛，自指涉性。那么这个 V 这个集合，clearly V belongs to V，V 属于 V。但是呢，the set of all sets leads to contradictions of its own in a more subtle way。这个万集之集会自己导致一个矛盾，而且是以一种更微妙的方式导致矛盾。这在习题 3\.3 和 3\.6，我们到时候就会看到了，这是卖关子啊。How is this contradiction resolved？上述矛盾如何被解决呢？

We assume that we have a set R。我们现在假设有一个集合 R，它被定义为 the set of all sets which are not elements of themselves——不是万集之集，而是上面符合上述定义的那个集合，也就是由所有不是自己要素的集合所构成的集合。并且我们作了这样的假设之后，立刻推出了一个矛盾；这个矛盾是这个 R 的集合定义的一个直接后果、直接推论，直接会导致这么一个矛盾。

啊，就是上面说过了，他把这个过程重新说了一遍。This can only mean that there is no set satisfying the definition of R。这只能表明，不存在符合 R 的定义的集合。In other words，换句话说，this argument proves that there exists no set whose members would be precisely the sets which are not elements of themselves。上述论证证明了：不存在这样的集合，它的组成部分或要素恰恰就是那些不是自身要素的集合。也就是说，不存在 R 这样的集合了。这其实已经用归谬法证明了：如果有 R，他妈的就会矛盾，所以不存在 R。R 就是这样的集合：它的要素是那些不是自身要素的集合；由这些集合所构成的这么一个集合不存在。The lesson contained in Russell's paradox and other similar examples——这个教训、这一课或者说这个道理，就包含在罗素的悖论、理发师悖论，以及自指涉悖论等其他类似的例子当中。Is that by merely defining a set we do not prove its existence？

这个道理就是说，仅仅通过定义一个集合，we do not prove its existence。如果你只是定义一个集合，却不能证明它的存在，那么我们是不能够证明它的存在的，不能证明它的实存，不能证明它实际上在现实当中站得住脚。罗素悖论和其他类似的例子教给我们的一课就是：只去定义一个集合，不足以证明它的实存。你定义的这个集合，不代表你已经证明了它的实存、它能够站得住。Similarly，as by defining a unicorn we do not prove that unicorns exist。

但是这里的这个例子——unicorn 和 existence 那个——直接就可以说：操，那你集合和你所设想的一个集合，和独角兽是同一种东西吗？独角兽是有它的表象化的，或者有它的幻想性，就在这里。就是说，数学家的哲学能力弱了就不管了，他这傻逼了，我操，whatever。

There are properties which do not define sets。就是说，存在一些属性，它们并不能用来定义集合，是这个意思。也就是说，it is not possible to collect all objects with those properties into one set。换句话说，有一些属性，你没有办法用这些属性把所有的对象收集到一个集合里面去。确实有一些属性，懂了吧？比如说，有一些属性就是“它自己不是它自己的要素”，这是一个属性，但你没办法用这个属性来定义一个新的集合。你如果这样定义，定义出来的这个集合就是个非法的集合，是不成立的集合，懂了吧？就是确实有一些属性没法用来定义集合，明白吗？但是没办法。甚至我们可以说，无产阶级就类似于这样一个东西，或者否定性无产阶级，即现实的激进的否定性；这个属性也没有办法用来定义那个 sets，没办法用来定义集合。这个反正是革命理论了，不跟你们扯了。

This observation leaves set theorists with a task of determining the properties which do define sets。这么一个发现，就给集合论家们留下一个任务：要弄明白、要决定、要弄清楚哪些属性要刻画清楚，哪些属性可以用来定义集合，哪些不行，对不对？你至少得说清楚哪些属性可以用来定义集合。上面那个属性就肯定不行——上面那个属性就是“不包含自己为要素的集合”；那么这个属性就没有办法定义集合，是不是？所以集合论家就得去弄清楚哪些属性可以用来定义集合，哪些属性不能用来定义集合。Unfortunately，no way how to do this is known。但是非常不幸的是，没有办法知道怎么做到这一点。And some results in logic，especially in so\-called incompleteness theory，尤其是这个不完备性定理，被哥德尔所发现的 Kurt Gödel。

Gödel，那德语不知道怎么念，被这狗逼发现了这个定理；这个定理就已经告诉你做不到这一点了。Seem to indicate that——不是，它看上去好像在表明：A complete answer is not even possible。想要弄清楚哪些属性可以刻画清楚，搞出一个明确的标准，告诉你哪些属性可以用来定义集合，这本身是不可能的。

Therefore we attempt a less lofty goal。我们就是找一个更轻松的、更他妈的蛇皮一点的目标。Lofty，loft 就是休闲的嘛，崇高的、傲慢呢？

不是，loft 是什么意思？屋顶、阁楼；lofty 是崇高的，翻译成“更高的”吗？不管了，less lofty 就是不那么高的。因此我们尝试一个不那么高的目标——上面那个目标太高了，我们要找一个容易点的目标。We formulate some of the relatively simple properties of sets used by mathematicians as axioms\.

我们来表述一些相对简单的集合属性，这些属性被数学家当作公理。然后我们用集合论把这些公理表达出来，并检查所有定理是否都能从公理中逻辑地推出。他的意思是：我既然无法给出一个标准来描述所有可以构成集合的属性，那就先看看数学家已经当作公理使用的那些属性；先用集合论把这些公理表达出来，再看这些公理作为属性所给出的集合是不是合法的集合。

公理搞定之后，再来看引理和定理（theorem）。按照形式逻辑，从这些公理中推出引理和定理；这些定理作为属性所给出的集合，是不是也站得住？Since the axioms are obviously true and the theorems logically follow from them, the theorems are also true。因为大家都认为这些公理明显是真的、对的，所以按照形式逻辑的方式从公理中推演出来的定理也是对的；但它可能没那么明显，not necessarily obviously。We end up with a body of truth about sets which includes among other things the basic properties of natural, rational and real numbers, functions and orderings, etc\.

也就是说，我们最终会得到一系列关于集合的真理，a body of truth。这里包括自然数、有理数、实数等基本对象的定义和属性。这里的 property 是专门术语，指刻画一个集合共同点的属性；用这个属性构造出集合，集合中的要素就可以说被这个集合定义了。基本属性包括自然数、有理数、实数，以及自然数、有理数、实数上的函数和 orderings（序、序数等），反正都是数学构造。于是我们可以得到一系列由这些东西的属性所构成的集合，以及关于它们的真——到底是真还是假？But as far as is known, no contradictions，至少目前所知不能有矛盾。Experience has shown that practically all notions used in contemporary mathematics can be defined：经验表明，至少在操作层面，当代数学中使用的所有概念，或者说那些点子、想法、乱七八糟的东西，都是可以被定义的。

里面的所有观念、人脑中想出来的概念和术语，以及它们在公理体系中推演出来的数学属性，都已经展示出来，也被定义了。这里省略了 can be defined，意思是：在这样一个公理体系里，那些数学属性也是可以被定义的，whatever。而且它们是在经验中被展示出来的，究竟是什么样的属性也就展示出来了。In this sense，在这个意义上，公理化的集合论 serves as a satisfactory foundation for the other branches of mathematics：它作为一个令人满意的基础，可以为其他所有数学分支奠基。

集合论的一个功能，就是看我们能构造什么样的自然数模型、实数模型，然后把其中的公理都用集合论的方式表示出来；把公理、定理、数学构造都用集合表示出来之后，再看这个集合有没有矛盾、站不站得住。如果没有矛盾、站得住，那就说明这些公理站得住，或者你能证明它一直是真的，那它就可以用来为数学奠基。On the other hand，另一方面，we do not claim that every true fact about sets can be derived from the axioms we present：我们并不宣称每一个关于集合的真的事实都能从我们给出的公理中派生出来。The axiomatic system is not complete in this sense。

也就是说，这个集合论的公理体系在这个意义上并不是完备的；And we return to the discussion of the question of completeness in the last chapter，关于完备性的讨论会在最后一章进行。这并不是说，我们给出的集合论公理体系或这些公理意味着：所有数学中的真的事实，比如某一个数学定理，都一定可以从最基本的数学公理出发，经过定理、引理等一步步推出来。所以这个公理体系在这个意义上不是完备的，它不能涵盖一切真命题，不能涵盖一切数学真命题。这就是贪得无厌嘛。

这个公理体系就相当于玩游戏：你按照这个套路玩，玩出来的肯定都是成就，游戏里好的剧情反正都能玩到。但这并不意味着，你要收集的所有好剧情、好要素，通过这种套路全能玩出来。达到全收藏、全成就？没这种说法。它的意思是，我们这一套办法没法让你拿到全成就、全卡牌收集，但可以让你杀上天梯榜前十名，那没问题。简单就这样理解。

第二节讨论属性。In the preceding section we introduced sets as collections of objects having some property in common：上一节我们把集合引入为拥有共同某种属性的一些对象所组成的集体。The notion of property merits some analysis，属性这个概念值得加以分析。日常语言中的一些属性太模糊，很难被数学理论接受。比如“屁股大”就无法当作数学理论中的属性来刻画数学对象、建构数学集合，因为“多大算大”并不清楚：臀围和腰围占比多少才算大？不清楚。Consider for example：我们来考虑 the set of all the great twentieth\-century American novels，也就是所有伟大的二十世纪美国小说的集合。

什么叫“伟大的美国小说”？这个标准很模糊。“二十世纪”也很模糊：是说作家出生在二十世纪吗？出生在1899年算不算？还是割脐带时是1900年或1901年？还是喊出第一声？还是从产道出来的一瞬间？到底怎么算？这些都很模糊。Different persons' judgments as to what constitutes a great literary work differ so much\.

他是个数学家，所以水平不够高。他会说什么？什么是一部伟大的文学作品？这个标准很模糊。我告诉你，“二十世纪”的标准也很模糊。比如时区划分：按照时区划分，在划分线上到底算几点？这又很模糊。你的手机在这里收到信号，是那边发出来的，还是显示屏上显示的，还是人读取到的时间数？连时间本身的确定都很模糊。反正懂了就没意思了。

这种自然语言、日常语言所描述的属性很含混。There is no generally accepted way how to decide whether a given book is or is not an element of the set：不存在一个普遍接受的方式来决定一本书是不是这个集合的要素。它到底是不是“二十世纪美国伟大小说”？不能确定。For an even more startling example，更令人吃惊的例子：考虑 series of those natural numbers which could be written down in\.\.\. 什么 notation？十进制，十进计数法。也就是说，考虑所有可以用十进制计数法写出来的自然数所构成的集合。

这里又加了括号，什么叫“可以”（could）？我们的意思是 someone could actually do it with paper and pencil，也就是能够用纸和笔写下来。Clearly zero can be so written down：很明显，零可以这样写下来。但其实零也写不下来——你没有办法写出一个完美的零，you understand？你只能用铅笔划一圈，用放大镜一看，它那个也是裂开的，是不是？

他说，零甚至不能完美地写在一个平面上。这个人是个数学家，没有什么哲学功底。不管了，我们不是那种抠牛角尖的人。他说，很明显零可以写下来：if number n can be written down, then surely number n plus one could also be written down。这里马上就有矛盾了：如果一个数可以被写下来，那么比它大一的数也可以写下来，而且可以轻而易举地写下来，这样就没完没了。你可以想象另一个写得稍快一些的人，或者一个有能力写得更快的人。无论他怎样稍微快一点，只要能写下一个数，比如九万九千九百九十九亿的九十九亿次方，只要有一个人能把这个数写下来，那么比他写得稍快一点的人也能把下一个数写下来。这样一来，一切数都能被写下来。Therefore, by the familiar principle of induction, every natural number，通过归纳法，每一个自然数都可以被写下来。但这明显不对。一个超级大的数，写起来真是要命。But that is plainly absurd to write down, say, ten……这个次方不知道怎么说，n 次方英语怎么说？

他接着说，这个数完全写不下来；即便写成 ten to the power of ten 这样的形式，也完全写不下来。按他的估算，要连续写三百年。你真要去算这个东西吗？如果每秒钟只写一个零，那算是手残；如果写快一点，一秒钟写十个零，也要写三十年。差不多就是这个意思。这样搞就很荒谬。问题的根源在于 could 的意义含混。

也就是说，could 是一个情态动词，它的用法和意义都比较含混。要避免类似的困境，我们现在必须非常清楚地描述：我们使用一个属性到底意味着什么。Only clear mathematical properties are allowed。只有清楚明白的数学属性才被允许。你看，这里就体现出分析哲学所喜欢的‘清楚明白’，对不对？这是因为工作上的困难所导致的，没办法。只有清楚明白的数学描述、数学属性才被允许。

非常幸运的是，these properties are sufficient；这样的属性是充足的。它们足以表达所有——这里的 all 要加引号——基本上所有的数学事实，都可以用这些清楚明白的数学属性来刻画。我们在这一节的阐释是非正式的（Our exposition in this section is informal）。读者如果想看这个话题如何从更严格的观点来研究，可以查阅一些数理逻辑的书。若要更严格地讨论上述问题，可以看数学哲学或分析哲学的书，从更严格的观点来研究这个话题。一个基本的、本质的逻辑属性是 membership property。

最基本的集合论属性是 membership，也就是成员性、要素性，即‘什么属于什么’。集合被定义成含有一些成员或要素，所以它最基本的属性就是 membership。你什么属性都没有，但至少还有 membership，至少还有这个会员资格。只要有一个集合，集合里的东西就都具有一个属性：它是这个集合的成员（it's a member of this set），也就是‘什么什么 is a member of 什么什么’。我们用‘属于’、belong to 来标记它。So x belongs to y reads: x is an element of y, or x is a member of y, or x belongs to y。这些表达式中的字母 x 和 y 是 variables，也就是变元。

他接着强调，集合论和思维、社会学的关系非常紧密。因为阶级革命中一个很重要的话题正是：无产阶级到底是不是资产阶级社会的成员？希望大家学集合论时不要忘记，现代资本主义社会中有一种认同困境。接着他说，学习这些工具性的东西时，虽然其中有很多所谓客观中立的工具性假设，但你要意识到，这样的东西并不是完全干净的；这种完全标准化的集合论内部就有很多资本主义的意识形态前设。但这并不意味着它就是大毒草，也不是这个意思，它仍然能用。然后继续看：集合论有高级版本，即融合了结构主义、辩证法的高级版本，比如拉康的体系。它讲究符号学和发生学。而前面这种集合论没有符号学和发生学，它先给你预设好符号系统，预设好 membership、belong、belongness 这种属性关系。

他继续回到变元：x 和 y 在这些表达式中是变元（variables）；they stand for / denote，也就是代表或表示。denote 在这里就是标记、记下来。这里还可以联系到十进制计数法：decimal notation，notation 就是计数法、记的办法。所以 x、y 代表、标记或记下某个 unspecified（非特定的、任意的）集合。它们是变元；x、y 代表任意集合，不确定是哪一个集合。arbitrary 在这里就是‘任意的’，即任意的集合。命题 x belongs to y 成立或不成立，完全取决于 x 和 y 所代表的集合（denoted by x and y）。x 是否属于 y、这个命题站不站得住，取决于 x、y 记的到底是哪个集合，所以变元是不确定的。

我们有时会说，x 属于 y 是 x 和 y 的属性；也可以说 y 有一个属性，就是有一个 x 属于它。总之，它是 x 和 y 的一个属性。读者对这种非正式说法应该很熟悉，因为其他数学分支也有这种说法。比如 m 小于 n 就是 m 和 n 的属性。这里的‘我们’不是指集合论家，而是指普通人；一般人有时会说 x 属于 y 是 x 和 y 的属性，这是一种不正式的说法。m 和 n 是表示不确定的数的变元。他不喜欢把 denote 翻译成‘指称’，更愿意翻译成‘标记’、‘标志’、‘指示’或‘表示’。它们是用来表示不确定的数的变元。有的 m 和 n 有 m 小于 n 这个属性，有的没有。比如 2 小于 4，所以 2 和 4 有这个属性；但 3 和 2 就不具有这个属性。

所有其他集合论属性，都可以借助逻辑手段、逻辑工具（形式逻辑或数理逻辑）从 membership 表达出来。所有的集合论命题都是‘什么属于什么’、‘什么不属于什么’、‘什么属于什么且什么属于什么’，等等。除了逻辑算子——即‘如果……那么……’、‘并且’、‘非’这些逻辑连接词——之外，集合论里只有一个算符，就是‘属于’，也就是 membership，它是最基本的。所有其他集合论属性都可以加上逻辑算符来表达；逻辑算符只包括同一性 identity、逻辑连接词和逻辑量词，也就是数理逻辑里那几个基本的东西。其实逻辑连接词只要两个就行了，就是‘非’和‘并且’；任意两个可以推出其他的。以及量词 quantifiers。

这里还涉及量词（quantifiers）。并不是所有逻辑连接词都能推出其他连接词；哪些能推出哪些，你们可以自己画个表，它是可以推出来的。其实逻辑连接词的功能就是一个矩阵，明白吧？所谓逻辑连接词就是二进制矩阵，比如写成 110、101、1000、1001、0010 这样的二进制矩阵。它就是由 0 和 1 组成的矩阵，你懂这个意思吧？

然后再把量词和同一律（identity）加上，也就是相等。它只需要这些逻辑符号：逻辑运算，加上包含，再加上 membership（属于），就能推出所有集合论的属性。We often speak of one and the same set in different contexts and find it convenient to denote it by different variables\.

集合论家常常会讨论同一个集合，只是在不同的语境下讨论同一个集合，并发现可以用不同的变元来指代它、标记它。这种情况下，我们就用等号来表明这两个变元实际上指同一个东西。这里把 variables 翻译成“变元”未必合适；它不是运算元，也不是变量。反正有时候我们用 x 表示这个集合，有时候用 y 表示这个集合，但它其实是同一个，于是就用等号来标记它是同一个。So we write x equals to y if x is identical with y\. 不过这里可能不能翻译成 equals to，可能要用三个横杠。先不管这个，这可能只是标记问题。也就是说，x is identical with x。这个等号不是数学里的相等号，而是等同号，应该念成 x is identical with y；if x is the same set as y, x is identical with y，也可以念成 equals to。先不管了。In the next example we list some obvious facts about identity\.

下面举一些关于等同关系的明显例子。首先是 x=x，x is identical with x；这是一个逻辑公式，而不是同一律。然后是：如果 x=y，那么 y=x，这是对称性。再就是可传递性：如果 x=y、y=z，那么 x=z。还有替换关系：如果 x=y，且 x∈z，那么 y∈z；集合关系也因此被传递过去：x 和 y 相等时，x∈z 就相当于 y∈z。反过来也一样。这些用直观就够了，不用论证。如果 x=y，那么有个东西属于它，这个东西也会属于与它等同的那个东西。

接下来讲属性（properties）。逻辑连接词可以用来从较简单的属性构造更复杂的属性。They are expressions like not\.\.\., and\.\.\., if\.\.\. then\.\.\., and if and only if\.\.\.，也就是“非……”“……并且……”“如果……那么……”以及“当且仅当……”。举个例子：x∈y 或 y∈z is a property of x and y，也就是 x 和 y 的一个属性。这里接着讲 or，用 or 来构造集合论的一个属性。

接着要问：这个 or 是否包含“同时相等”的情况？也就是说，如果 x∈y 或 y∈x，它包不包括 x∈y 且 y∈x，也就是 x=y 这种情况？有的版本写清楚了，有的没有；这要看它有没有写明。先不管这个问题。然后是 not：not x belongs to y and not y belongs to x，即并非 x∈y，并且并非 y∈x。用更惯用的英语说，x is not an element of y and y is not an element of x，这也是 x 和 y 的一个属性。也就是说，x 不是 y 的要素，y 也不是 x 的要素；这也可以被构造成 x、y 的一个属性。再看：if x equals y, then x belongs to z if and only if y belongs to z, is a property of x, y and z。这个是对的。它只不过是把上面那句话、把第二点一里的 d 拿过来。原句里包含 if\.\.\. then\.\.\.，而这里把它变成了 if and only if；原句只给了一个 if\.\.\. then，并没有说 if and only if，对不对？它没有说这个。若说当且仅当，那就是右边也可以推过来；当且仅当的意思是，它可以推出它；如果它不成立，那么它也不成立。这就是 if and only if。算了，不管了。这里不是让你研究这些命题本身，它只是用来告诉你：加上逻辑连接词，再加上等于关系，就可以给出一些更复杂的集合论属性。

X is not an element of X，也就是 X 不是 X 的要素；也可以表示成并非 X 属于 X，这是 X 的一个属性。我们写作 X doesn't belong to Y，而不写“并非 X 属于 Y”：为了标记方便，直接把否定词放到后面，写“X 不属于 Y”；同样，不写“并非 X 等于 Y”，而把否定词移到等号上，写成“X 不等于 Y”。

第三部分是量词：quantifiers for all and for every，以及 there is / there exists，它们提供 additional logical means，也就是额外的逻辑含义。量词主要有两个：全称量词和存在量词。Mathematical practice shows that all mathematical facts can be expressed in the very restricted language we just described：数学实践已经表明，所有数学事实都可以用我们刚刚描述的那种非常受限的语言、用数理逻辑来表达。但这种语言不允许模糊表达，比如本节开头提到的“伟大的美国小说”之类。下面看一些包含量词的属性例子。Example: there exists y belongs to X，即存在 y 属于 X。还有 for every y belongs to X：对于每一个属于 X 的 y，都有一个 z，这个 z 属于 x，并且 z 属于 y。另一个是 there exists z such that z belongs to x and z does not belong to y，即存在 z，这个 z 属于 x，但 z 不属于 y。

一个命题的真假当然取决于集合。就前面的 a 句“存在 y 属于 x”来说，它是真还是假，很明显取决于由变元 x 所指、所标志的那个集合，完全取决于 x，取决于 x 里面到底有没有 y。这句话是对还是错，归根结底取决于 x 里面到底有没有 y。For example, if x is the set of all American presidents after 1789。如果 x 是所有 1789 年之后美国总统的集合，那么 a 就是错的，因为按他的说法，x 里面没有 y、不存在 y；这个意思就是 x 是空集合。这个例子说的好像是 1789 年之前，那就还存在；there exists y belongs to x，这很明显，因为这些人（或这些总统）都已经死了。我的意思是，a 很明显找不到合适的 y，因为这是个空集合。Generally，不过数学家也不总是特别聪明。那我说，这个集合里可以是一些人的名字，或者这些人的历史——历史上的这些人，作为死人，或者作为共同体想象、回忆中的这些人被记录下来。Generally, a is true if x has some elements：一般来说，如果 x 含有某些元素，a 就为真。

如果 x 是空集，A 就为假；如果 x 不是空集，A 就为真。因为这里没有进一步刻画 y，y 只表示“存在某个要素”，所以只要 x 非空，就可以说 A 是对的。也就是说，A 是 x 的一个属性，或者说 A 取决于参数 x。

同样，B 是 x 的属性，C 是 x 和 y 的属性。B 只取决于 x 这一个参数；C 则取决于 x 和 y 两个参数。要注意，y 并不是 A 中的参数：把 y 换成别的字母，A 这句话并没有实质影响。A、B、C 都是用来刻画集合、刻画一堆要素的。A 刻画出来的是一堆非空集合构成的集合；A 最终只是用来描述 x，和 y 没有关系。B 同样只刻画 x：它描述一堆集合 x，并对 x 的每一个要素提出要求；至于 y 到底是什么，B 并不管，因为它并没有刻画 y。

比如有一个集合 u，里面有一堆 x1、x2、x3……这些 x 的共同属性是：每个 x 都有 y∈x，也就是它们都是非空集合。因此 A 刻画的正是非空集合；A 只描述 x，跟 y 没有关系。y 只是一个用来标记的符号，它没有指向什么，也没有约束什么。B 同样只刻画 x：它描述一堆集合 x，要求 x 的每一个要素满足某个条件；至于 y 到底是什么，B 不管，因为它没有刻画 y。C 的要求则是：如果有 z 属于 x，那么 z 也得属于 y。这个构造很麻烦。可以把 x 想成一个大盒子，里面有很多小盒子，每个小盒子都是 y；要求只要大盒子里存在一个小盒子，这个盒子既是大盒子的要素，又是每个小盒子的要素。

这个要求在逻辑上不太可能，对吧？这需要证明。B 也是对大盒子 x 提出某种要求；所以可以说 B 只刻画 x。B 只约束 x，而 C 既约束 x，也约束 y。接下来看 A 这个属性：去探究 A 对某个特定 y 是否成立，是没有意义的。量词里的 y 只是为了方便，我们也可以说存在 w∈x，或者直接说存在 x 的某些要素，用 some elements 来代替 y。同理，B 不是 y 或 z 的属性，C 也不是 z 的属性。这些都可以当作习题去证明，也就是证明 y 可以是任意的东西、任意的集合，或者任意要素。你甚至可以用反证法，但其实没有必要；它就是那样定义的。

虽然判定一个给定属性有哪些参数的精确规则可以很容易表述、很容易形式化地写出来，但我们还是依靠读者的常识，并且只再举最后一个例子。也就是说，这个工作我不做，只举最后一个例子；更多的是让读者用自己的常识、自己的 common sense 去判断：在一个属性的描述中，到底哪些是参数，哪些不是参数。所谓 common sense 就是常识，是大家都有的通用官能、基本头脑，你自己去判断。

然后他给出例 2\.4，也就是 A、B、C 三个例子。这里的 y belongs to x 还是让你做习题。A is a property of x and y：在这里，A 是 x、y 的属性，It is true for some pairs of sets x, y and false for others。这里 y 和 x 都是它的参数。因为这样说的时候没有引入量词，直接说 y 属于 x，它约束的是 y、x 组成的对子：集合 y 和集合 x 一个属于另一个，这一对集合符合这个关系，才符合这个描述。所以它里面有两个参数。B 说 there is y belongs to x，也就是前面讲的那种情况，只不过把 exists 换成了 is；它只针对 x，只有一个参数 x。意思仍然是 x 要有要素；它只刻画 x，并没有刻画 y。也就是说，B 是 x 的属性，不是 y 的属性；而 C 没有参数。C 是 for every x there is y belongs to x：对每一个 x，都存在一个 y 属于 x。这里没有说清楚 x 是什么样的，但 C 要么真要么假。

对于每一个 x，存在一个 y 属于 x。这里的量词是“对每一个什么样的 x”呢？他没有说清楚。对每一个 x，都存在一个 y 属于 x，也就是 For every x, there is\.\.\.

这个 C 就是两个量词堆叠。把它写出来，就是“∀x，存在 y∈x”，后面没有别的了。你如果学过数理逻辑，就会看到它只是写了两个量词，后面什么都没有写，所以它本身不能算是一个描述。要看它到底有没有参数，就要看它能不能写成一个数理逻辑表达式。因此，它要么为真，要么为假；事实上，正是没有参数的属性，才因此要么为真、要么为假。

没有参数的这些属性，本身就有真假，因此被称为 statements（表述）。所有数学定理都是 statements，而且是真的 statements。它的真假不取决于 x 怎么样，也不取决于 y 怎么样。例如 for every x, there is\.\.\.

就是这句话，这个英语表达，我们不是英语国家的人，看它也很别扭：“对于所有的 x，there is y belongs to x。”我就是弄不懂这句话——它是在约束这个 x 吗？后面这个东西是用来描述、限制这个 x 的吗？这句话令人头疼，因为我不知道后面这部分是不是用来描述这个 x 的。

如果它的意思是“对于所有的非空集合 x”，那 C 就完全可以变成 for every nonempty set。可后面呢？没有下文了。C 就成了一句空话：对于每一个非空集合，然后呢？或者说，对每一个东西都加上“它是非空集合”这个条件，这不是废话吗？后面没有“怎么样”了。There is 后面也没有怎么样了。所以它没有办法用来表达什么，也不取决于任何一个东西，没有真、没有假可言。

举个例子，如果这里的 x 是空集，那么 C 就不再是“for every x”了：空集不被包含在前面这个 x 的范围里。也就是说，这句话没有办法让 x 是空集。再比如 B，也就是“存在 y 属于 x”这个属性：如果 x 是空集，那么 B 就是错；如果 x 不是空集，那么 B 就是对。它能判定对错。也就是说，空集不具有这个属性，而非空集具有这个属性。所以 B 有一个参数 x；x 非空时，B 对 x 成立，x 为空时，B 对 x 不成立。至于 C 这句话，如果 x 是空集，它跟 x 就没有关系了：C 预先把空集排除掉了，空集不在 every x 里面。

反过来，如果你说 for every x，并且假设 x 是非空集，there is\.\.\.，那就不能说 C 是对的。因为 C 本身只是个 whatever，只是一个限定条件；如果 x 是空集，这里还要算。对每一个非空集，存在 y 属于它；对每一个空集，存在 y 属于空集——for every\.\.\. 如果它是空集，它就不符合这个描述。我会觉得 C 会出现这种情况：for every x，如果这里是非空的，后面这句话就根本没法写出来。

不管了。数学中，有时我们想指称一个任意、未指定的属性。这时会用粗体大写字母来表示 statements 和 properties，并在方便时列出部分或全部参数。也就是说，我们会用加粗的大写首字母，也就是 bold face（黑体、粗体），来指示 statements 和 properties，或者说表示一些表达式；如果方便，就把部分或全部参数写在括号里。A\(x\) 表示任意一个以 x 为参数的属性。比如 A、B、C，或者 2\.3 里的 C，只要列出一个就行，不必全部列出。以 x、y 为参数的属性，比如 2\.3 中的 C，或 2\.4 中的 A；2\.4 还举了 D 这个例子，即 x∈y，或 x=y，或 y∈x。

一般地，p\(x,y,…,z\) 是一个属性，它的真假取决于参数 x、y、z，可能还取决于其他参数。我们反复强调，所有集合论属性都可以用我们这种受到严格限制的语言来表达；这种语言只由 membership（属于关系）以及逻辑运算、逻辑方法构成。无论如何，随着集合论的发展，越来越复杂的定理被提出、证明和给出。

因此，为各种特殊属性命名是很实际、很实用的做法：我们可以定义新属性，引入一个新符号来标记这个属性，把它看作明确写法的 shorthand（缩写）。例如子集关系：X 是 Y 的子集，当且仅当 X 的每个元素都是 Y 的元素。它是 X 和 Y 的属性；在更复杂的表述中，只要愿意，随时可以用它的定义替换 X⊆Y。比如“若 X⊆Y 且 Y⊆Z，则 X⊆Z”，展开定义就是：若 X 的每个元素都是 Y 的元素，且 Y 的每个元素都是 Z 的元素，则 X 的每个元素都是 Z 的元素。你可以用缩写，但只要需要，都可以用定义来代替这个缩写，把缩写换回定义。

显然，没有定义，数学仍然可以开展，但会极其笨拙（clumsy）。笨拙就是不好用。也就是说，数学可以不用定义，但没有定义的数学会太笨拙；把内容都展开写，就会非常笨拙。

把内容写成这样确实太笨拙了。另一种定义方式是：考虑属性 P\(x\)，即不存在 y 属于 x。满足这个属性的 x 就是空集，写作 x=∅。

这个属性是说，集合 x 没有元素，也就是不存在任何 y 属于 x。换句话说，集合 x 里没有任意的 y，没有要素；这是一个属性。我们在第三节会证明：存在一个集合 x，使得 P\(x\) 成立，也就是存在一个没有元素的集合。第三节还会证明：至多有一个集合 x 满足 P\(x\)，也就是说，符合这一属性的集合只有一个，这个唯一的集合就是空集。更具体地说，如果 P\(x\) 并且 P\(x'\)，那么 x 和 x' 是同一个集合。若集合 x 满足 P\(x\)，集合 x' 也满足 P\(x'\)，则 x 与 x' 相同。这个 x' 该怎么念呢？

这个符号念作 X prime（X'）；一般念 prime，还有 double prime、triple prime 等。如果 X' 也满足 P，那么 X 和 X' 就是同一个集合。若 X 没有元素，并且 X' 也没有元素，那么 X 和 X' 相同。条件 A 和 B 合在一起表达的事实是：存在一个唯一的集合 X 满足 P\(X\)。这样我们就可以给这个唯一的集合一个名字，称为 empty set，也就是空集，并在更复杂的表达式中使用它。“empty set is subset of Z”的意思是空集是 Z 的子集；完整地说，没有元素的集合 X 是 Z 的子集。我们偶尔也会把空集称为由属性 P 定义的一个常量。

这里所说的 constant，并不是数学计算意义上的“常数”。你们中绝大多数人先学数学、再学数理逻辑，所以容易把 constant 翻成“常量”，把 variables 翻成“变量”。其实它更像一个思辨的单位。用黑格尔辩证法的方式描述，constant 可以说是一个“恒长者”，variable 是一个“可变者”。注意不要把它理解成“量”，它不是量；它更像运算的单位，或者说是思考的单位，甚至不是计算意义上的东西。因此这里把它理解为某种不变的东西，而不是“常量”。

最后一个关于定义的例子，是考虑属性 Q\(x,y,z\)，它涉及 x、y、z 三个参数。这个属性说：对每一个 u，u 属于 z，当且仅当 u 属于 x 并且 u 属于 y。也就是说，u 必须是 x 和 y 的公共元素。因此，z 是这样一个集合：它的每一个元素都是另外两个集合的公共元素。x 和 y 则各自要与另一个集合有公共元素；而 z 的每一个要素都必须是另外两个集合的公共要素。这个属性刻画了三个集合。

更准确地说，这个属性其实描述了两类集合：x 和 y 在某种意义上是对称、平等的；z 与 x、y 属于不同的描述类型，但 x、y、z 在这个属性中都被刻画了。对 x 或 y 来说，它只需要有某个要素成为另一个集合的公共要素，甚至成为另外两个集合的公共要素；对 z 来说，它的所有要素都必须是另外两个集合的公共要素。下一节会看到：对任意的 x 和 y，都存在一个 z 满足 Q\(x,y,z\)。也就是说，对每一个 x、每一个 y，都会存在一个 z 满足 Q\(x,y,z\)。这个结论其实比较好证明，它算是集合论的一条公理。注意这里是“当且仅当”：如果 x 和 y 没有公共要素，那么前面的条件就不成立。

它并不是说一定要有公共要素，而是“当且仅当”：只要 x 和 y 有公共要素，就会存在这样的 z。这个 z 是可以证明存在的，你可以构造一个 z 出来，z 里面反正就是 x 和 y 的交集。然后条件 B 说的是交集的唯一性：两个集合如果有交集，那个交集只能是同一个，不能有两个交集。也就是对任意的 x 和 y，至多存在一个 z 满足 Q\(x,y,z\)。条件 A 和 B 合在一起保证：对每一个 x 和 y，存在唯一的集合 z 满足 Q\(x,y,z\)。A 保证如果有公共元素，就能构成一个交集、成为一个集合；B 保证如果存在交集，那就只有一个、同一个交集。

因此，对于这个唯一的集合 z，我们可以引入一个名字：x ∩ y，也就是 x 与 y 的 intersection，即交集。Q\(x,y,z\) 说的就是“x 和 y 的交集是 z”，所以这个说法站得住。我们把这个东西称为由性质 Q 定义的一种运算。到这里，它就是在逐层地定义集合论里面的一些基本概念。

我讲了两个小时吧，正好两个小时。到这里，它逐层定义了什么是属性，以及集合论的一些基本构造和表述。今天就讲到这里。
